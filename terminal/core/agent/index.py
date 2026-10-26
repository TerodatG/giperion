# Giperion/terminal/core/agent/index.py                                v001
# Индекс проекта: файлы и символы Python для быстрого поиска.
# Последнее изменение: первый вариант — AST-обход и кэш в data/.

import ast
import re
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
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
MAX_HEADINGS = 200

# Кэш в памяти: 307 КБ JSON не перечитываются на каждый find_symbol.
_INDEX_CACHE: dict[tuple, dict] = {}


def _index_stamp() -> tuple[int, int] | None:
    """Отпечаток файла индекса: время и размер."""

    try:
        stat = INDEX_FILE.stat()
    except OSError:
        return None

    return (stat.st_mtime_ns, stat.st_size)


def _cache_index(base: Path, document: dict) -> None:
    """Кладёт документ в кэш и убирает старые версии этого индекса."""

    prefix = (str(base), str(INDEX_FILE))

    for key in list(_INDEX_CACHE):
        if key[:2] == prefix:
            del _INDEX_CACHE[key]

    _INDEX_CACHE[(*prefix, _index_stamp())] = document


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


def _headings_of(text: str) -> list[dict]:
    """Заголовки markdown как «разделы» для поиска."""

    found = []

    for number, line in enumerate(str(text).splitlines(), start=1):
        match = HEADING.match(line.strip())

        if not match:
            continue

        found.append(
            {
                "name": match.group(2).strip(),
                "kind": "section",
                "line": number,
            }
        )

        if len(found) >= MAX_HEADINGS:
            break

    return found


def _is_index_file(path: Path) -> bool:
    """Сам файл индекса не считается частью проекта."""

    try:
        return Path(path).resolve() == Path(INDEX_FILE).resolve()
    except OSError:
        return False


def build_index(root: Path) -> dict:
    """Строит индекс заново и сохраняет его в data/agent_index.json."""

    base = Path(root).resolve()
    files: dict[str, dict] = {}
    symbols: list[dict] = []

    for path in tools._iter_text_files(base):
        if _is_index_file(path):
            continue

        try:
            stat = path.stat()
        except OSError:
            continue

        relative = path.relative_to(base).as_posix()
        files[relative] = {
            "mtime": int(stat.st_mtime),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }

        suffix = path.suffix.lower()

        if suffix not in (".py", ".md"):
            continue

        if stat.st_size > MAX_FILE_BYTES:
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if suffix == ".py":
            items = _symbols_of(path, text)
        else:
            items = _headings_of(text)

        for item in items:
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


def _files_changed(base: Path, document: dict) -> bool:
    """Изменился ли проект с момента сборки индекса."""

    stored = document.get("files")

    if not isinstance(stored, dict):
        return True

    seen: set[str] = set()

    for path in tools._iter_text_files(base):
        if _is_index_file(path):
            continue

        relative = path.relative_to(base).as_posix()

        try:
            stat = path.stat()
        except OSError:
            return True

        entry = stored.get(relative)

        if not isinstance(entry, dict):
            return True

        stamp = entry.get("mtime_ns")

        if stamp is None:
            stamp = int(entry.get("mtime", -1)) * 1_000_000_000

        if int(stamp) != stat.st_mtime_ns:
            return True

        if int(entry.get("size", -1)) != stat.st_size:
            return True

        seen.add(relative)

        if len(seen) > MAX_FILES:
            break

    return len(seen) != len(stored)


def load_index(root: Path, refresh: bool = False) -> dict:
    """Читает кэш индекса или строит его, если проект изменился."""

    base = Path(root).resolve()
    cache_key = (str(base), str(INDEX_FILE), _index_stamp())

    if not refresh:
        cached = _INDEX_CACHE.get(cache_key)

        if cached is not None and not _files_changed(base, cached):
            return cached

    document = read_json_object(INDEX_FILE)

    fresh = (
        not refresh
        and str(document.get("root")) == str(base)
        and isinstance(document.get("symbols"), list)
        and isinstance(document.get("files"), dict)
        and not _files_changed(base, document)
    )

    if fresh:
        _cache_index(base, document)

        return document

    document = build_index(base)
    _cache_index(base, document)

    return document


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
