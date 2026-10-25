# Giperion/terminal/core/agent/index.py                                v001
# Индекс проекта: файлы и символы Python для быстрого поиска.
# Последнее изменение: первый вариант — AST-обход и кэш в data/.

import ast
import time
from pathlib import Path

from config import DATA_DIR
from shared.storage.json_store import read_json_object, write_json
from terminal.core.agent import tools
from terminal.core.agent.protocol import ToolResult

INDEX_FILE = DATA_DIR / "agent_index.json"
TTL_SECONDS = 300
MAX_FILES = 4000
MAX_FILE_BYTES = 500_000
MAX_MATCHES = 30


def _symbols_of(path: Path, text: str) -> list[dict]:
    """Собирает классы и функции файла с номерами строк."""

    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []

    found: list[dict] = []

    def walk(node, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            name = getattr(child, "name", "")

            if isinstance(child, ast.ClassDef):
                full = f"{prefix}{name}"
                found.append(
                    {
                        "name": full,
                        "kind": "class",
                        "line": child.lineno,
                    }
                )
                walk(child, full + ".")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                full = f"{prefix}{name}"
                kind = (
                    "method" if prefix else "function"
                )
                found.append(
                    {"name": full, "kind": kind, "line": child.lineno}
                )
                walk(child, full + ".")
            else:
                walk(child, prefix)

    walk(tree)

    return found


def build_index(root: Path) -> dict:
    """Строит индекс заново и сохраняет его в data/agent_index.json."""

    base = Path(root).resolve()
    files: dict[str, dict] = {}
    symbols: list[dict] = []

    for path in tools._iter_text_files(base):
        try:
            stat = path.stat()
        except OSError:
            continue

        relative = path.relative_to(base).as_posix()
        files[relative] = {
            "mtime": int(stat.st_mtime),
            "size": stat.st_size,
        }

        if path.suffix.lower() != ".py":
            continue

        if stat.st_size > MAX_FILE_BYTES:
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for item in _symbols_of(path, text):
            symbols.append(
                {
                    "path": relative,
                    "kind": item["kind"],
                    "name": item["name"],
                    "line": item["line"],
                }
            )

        if len(files) >= MAX_FILES:
            break

    document = {
        "root": str(base),
        "built_at": int(time.time()),
        "files": files,
        "symbols": symbols,
    }

    try:
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        write_json(INDEX_FILE, document)
    except OSError:
        pass

    return document


def load_index(root: Path, refresh: bool = False) -> dict:
    """Читает кэш индекса или строит его, если он устарел."""

    base = Path(root).resolve()
    document = read_json_object(INDEX_FILE)

    fresh = (
        not refresh
        and str(document.get("root")) == str(base)
        and isinstance(document.get("symbols"), list)
        and isinstance(document.get("files"), dict)
        and time.time() - float(document.get("built_at") or 0)
        <= TTL_SECONDS
    )

    if fresh:
        return document

    return build_index(base)


def find_symbol(
    root: Path,
    query: str,
    limit: int = MAX_MATCHES,
    refresh: bool = False,
) -> ToolResult:
    """Ищет функции и классы по части имени."""

    needle = str(query or "").strip().casefold()

    if len(needle) < 2:
        return ToolResult(
            False,
            "Нужна часть имени не короче двух символов.",
        )

    index = load_index(root, refresh=refresh)
    symbols = index.get("symbols") or []

    matches = []

    for item in symbols:
        name = str(item.get("name") or "")
        lowered = name.casefold()

        if needle not in lowered:
            continue

        if lowered == needle:
            rank = 0
        elif lowered.split(".")[-1] == needle:
            rank = 1
        elif lowered.startswith(needle):
            rank = 2
        elif lowered.split(".")[-1].startswith(needle):
            rank = 3
        else:
            rank = 4

        matches.append((rank, len(name), item))

    if not matches:
        return ToolResult(
            True,
            f"Символ «{query}» не найден в индексе "
            f"({len(symbols)} символов, {len(index.get('files') or {})} "
            "файлов). Попробуй search_text.",
        )

    matches.sort(key=lambda row: (row[0], row[1], row[2]["path"]))

    lines = []

    for _rank, _length, item in matches[: max(1, limit)]:
        lines.append(
            f"{item['path']}:{item['line']}: "
            f"{item['kind']} {item['name']}"
        )

    header = (
        f"Найдено {len(matches)}, показано {len(lines)} "
        f"(индекс: {len(symbols)} символов).\n"
    )

    return ToolResult(True, header + "\n".join(lines))


def symbols_for_file(root: Path, path: str) -> list[dict]:
    """Символы одного файла — для тестов и отладки."""

    index = load_index(root)
    wanted = str(path).replace("\\", "/")

    return [
        item
        for item in (index.get("symbols") or [])
        if item.get("path") == wanted
    ]
