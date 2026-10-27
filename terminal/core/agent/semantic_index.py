# Giperion/terminal/core/agent/semantic_index.py                       v001
# Фрагменты проекта и их кеш для смыслового поиска.
# Последнее изменение: вынесено из semantic.py.

import ast
import hashlib
import os
import re
from pathlib import Path

from shared.storage.json_store import read_json_object, write_json
from terminal.core.agent import tools

MAX_CHUNKS = 6000
MAX_FILES = 4000
MAX_CHUNK_CHARS = 2400
MAX_CHUNK_LINES = 80
TEXT_WINDOW = 60
SKIP_PREFIXES = ("data/", ".agent_worktrees/", "archive/")
EXTRA_SKIP_DIRS = {"data", ".agent_worktrees"}
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

_MEMORY: dict[tuple[str, str], dict] = {}


def reset_cache() -> None:
    """Забывает построенные фрагменты в памяти."""

    _MEMORY.clear()


def _iter_files(base: Path):
    """Текстовые файлы проекта без data и worktrees.

    Обход собственный: tools._iter_text_files упирается в лимит
    MAX_SEARCH_FILES на служебных копиях и пропускает исходники.
    """

    skip_dirs = set(tools.SKIP_DIRS) | EXTRA_SKIP_DIRS
    seen = 0

    for folder, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(
            name for name in dirnames if name not in skip_dirs
        )

        for name in sorted(filenames):
            path = Path(folder) / name

            if path.suffix.lower() not in tools.TEXT_SUFFIXES:
                continue

            try:
                if path.stat().st_size > tools.MAX_SEARCH_FILE_BYTES:
                    continue
            except OSError:
                continue

            yield path
            seen += 1

            if seen >= MAX_FILES:
                return


def _is_cache(path: Path, skip_files: tuple[Path, ...]) -> bool:
    """Служебные файлы поиска не индексируются."""

    try:
        resolved = Path(path).resolve()
    except OSError:
        return False

    return any(resolved == Path(item).resolve() for item in skip_files)


def _skip(relative: str) -> bool:
    """Служебные каталоги не попадают в смысловой индекс."""

    return relative.startswith(SKIP_PREFIXES)


def _clip(lines: list[str], start: int, end: int) -> str:
    """Кусок файла по номерам строк с ограничением размера."""

    chunk = "\n".join(lines[start:end])
    chunk = chunk[:MAX_CHUNK_CHARS]

    return chunk.strip()


def _module_chunk(
    relative: str,
    lines: list[str],
    tree: ast.Module,
) -> list[dict]:
    """Docstring или шапка комментариев модуля."""

    end = 0
    nodes = getattr(tree, "body", [])

    if nodes:
        first = nodes[0]

        if isinstance(first, ast.Expr) and isinstance(
            getattr(first, "value", None),
            ast.Constant,
        ) and isinstance(first.value.value, str):
            end = int(getattr(first, "end_lineno", 0))
        else:
            for number, line in enumerate(lines[:20], start=1):
                if line.strip().startswith("#"):
                    end = number
                elif line.strip():
                    break

    body = _clip(lines, 0, min(end, 30)) if end else ""

    if not body:
        return []

    return [
        {
            "path": relative,
            "line": 1,
            "kind": "module",
            "name": Path(relative).name,
            "text": body,
        }
    ]


def _py_chunks(relative: str, text: str) -> list[dict]:
    """Функции, методы, классы и шапка модуля как фрагменты."""

    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []

    lines = text.splitlines()
    found = _module_chunk(relative, lines, tree)
    seen: set[tuple[int, int]] = set()

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        start = max(0, int(node.lineno) - 1)
        end = int(getattr(node, "end_lineno", node.lineno))
        span = (start, end)

        if span in seen:
            continue

        seen.add(span)
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        body = _clip(lines, start, min(end, start + MAX_CHUNK_LINES))

        if body:
            found.append(
                {
                    "path": relative,
                    "line": start + 1,
                    "kind": kind,
                    "name": node.name,
                    "text": body,
                }
            )

    return found


def _md_chunks(relative: str, text: str) -> list[dict]:
    """Разделы markdown: заголовок и текст до следующего заголовка."""

    found: list[dict] = []
    current: dict | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current is None:
            return

        body = "\n".join(buffer)[:MAX_CHUNK_CHARS].strip()

        if body:
            current["text"] = body
            found.append(current)

    for number, line in enumerate(text.splitlines(), start=1):
        match = HEADING_RE.match(line.strip())

        if match:
            flush()
            current = {
                "path": relative,
                "line": number,
                "kind": "section",
                "name": match.group(2).strip(),
            }
            buffer = [line]
            continue

        if current is not None:
            buffer.append(line)

    flush()

    return found


def _text_chunks(relative: str, text: str) -> list[dict]:
    """Обычный текст: окна по TEXT_WINDOW строк."""

    lines = text.splitlines()
    found: list[dict] = []

    for start in range(0, len(lines), TEXT_WINDOW):
        body = _clip(lines, start, start + TEXT_WINDOW)

        if not body:
            continue

        found.append(
            {
                "path": relative,
                "line": start + 1,
                "kind": "text",
                "name": Path(relative).name,
                "text": body,
            }
        )

    return found


def _chunks_of(relative: str, text: str) -> list[dict]:
    """Фрагменты файла по расширению."""

    if relative.endswith(".py"):
        return _py_chunks(relative, text)

    if relative.endswith(".md"):
        return _md_chunks(relative, text)

    return _text_chunks(relative, text)


def _payload(chunk: dict) -> str:
    """Текст, который идёт в эмбеддинги и BM25."""

    return (
        f"{chunk['path']}:{chunk['line']} "
        f"{chunk['kind']} {chunk['name']}\n{chunk['text']}"
    )


def _collect(
    base: Path,
    skip_files: tuple[Path, ...],
) -> tuple[dict[str, dict], list[dict]]:
    """Обходит проект: снимок файлов и фрагменты."""

    files: dict[str, dict] = {}
    chunks: list[dict] = []

    for path in _iter_files(base):
        relative = path.relative_to(base).as_posix()

        if _is_cache(path, skip_files) or _skip(relative):
            continue

        try:
            stat = path.stat()
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        files[relative] = {
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }

        if len(chunks) >= MAX_CHUNKS:
            continue

        for chunk in _chunks_of(relative, text):
            payload = _payload(chunk)
            chunk["payload"] = payload
            chunk["hash"] = hashlib.sha1(
                payload.encode("utf-8")
            ).hexdigest()[:16]
            chunks.append(chunk)

            if len(chunks) >= MAX_CHUNKS:
                break

    return files, chunks


def signature(chunks: list[dict]) -> str:
    """Отпечаток набора фрагментов для кеша BM25."""

    joined = "".join(chunk["hash"] for chunk in chunks)

    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def _build(
    base: Path,
    cache_file: Path,
    skip_files: tuple[Path, ...],
) -> dict:
    """Строит индекс фрагментов и сохраняет его."""

    files, chunks = _collect(base, skip_files)
    document = {
        "root": str(base),
        "files": files,
        "chunks": chunks,
        "signature": signature(chunks),
        "limit": MAX_CHUNKS,
    }

    try:
        Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
        write_json(cache_file, document)
    except OSError:
        pass

    return document


def _changed(
    base: Path,
    files: dict,
    skip_files: tuple[Path, ...],
) -> bool:
    """Появились, исчезли или изменились файлы проекта."""

    seen: set[str] = set()

    for path in _iter_files(base):
        if _is_cache(path, skip_files):
            continue

        relative = path.relative_to(base).as_posix()

        if _skip(relative):
            continue

        entry = files.get(relative)

        if not isinstance(entry, dict):
            return True

        try:
            stat = path.stat()
        except OSError:
            return True

        if int(entry.get("mtime_ns", -1)) != stat.st_mtime_ns:
            return True

        if int(entry.get("size", -1)) != stat.st_size:
            return True

        seen.add(relative)

    return len(seen) != len(files)


def load(
    root: Path,
    cache_file: Path,
    skip_files: tuple[Path, ...],
    refresh: bool = False,
) -> dict:
    """Кеш фрагментов; перестраивается при изменении файлов."""

    base = Path(root).resolve()
    key = (str(base), str(cache_file))
    cached = _MEMORY.get(key)

    if not refresh and cached is not None and not _changed(
        base,
        cached.get("files") or {},
        skip_files,
    ):
        return cached

    document = read_json_object(cache_file)
    fresh = (
        not refresh
        and str(document.get("root")) == str(base)
        and isinstance(document.get("chunks"), list)
        and isinstance(document.get("files"), dict)
        and int(document.get("limit") or 0) == MAX_CHUNKS
        and not _changed(base, document.get("files") or {}, skip_files)
    )

    if fresh:
        _MEMORY[key] = document

        return document

    document = _build(base, cache_file, skip_files)
    _MEMORY[key] = document

    return document
