# Giperion/terminal/core/agent/lsp_tools.py                            v001
# Инструменты LSP: диагностика, определения и ссылки.

import os
import shutil
from pathlib import Path

from terminal.core.agent.lsp_client import LspClient, LspError
from terminal.core.agent.protocol import ToolResult

# Своя команда сервера: «pylsp» или «pyright-langserver --stdio».
COMMAND_ENV = "GIPERION_LSP_COMMAND"

# Порядок автоопределения: первый найденный сервер и используется.
CANDIDATES = (
    ("pylsp", ()),
    ("pyright-langserver", ("--stdio",)),
    ("clangd", ()),
)

SEVERITY = {
    1: "ошибка",
    2: "предупреждение",
    3: "информация",
    4: "подсказка",
}

_CACHE: dict[tuple[str, tuple[str, ...]], LspClient] = {}


def server_command() -> list[str] | None:
    """Команда языкового сервера: из окружения или автоопределение."""

    raw = os.environ.get(COMMAND_ENV, "").strip()

    if raw:
        return raw.split()

    for name, args in CANDIDATES:
        found = shutil.which(name)

        if found:
            return [found, *list(args)]

    return None


def client_for(root: Path) -> LspClient:
    """Клиент для проекта (переиспользуется между вызовами)."""

    command = server_command()

    if not command:
        raise LspError(
            "LSP-сервер не найден: установи pylsp "
            f"или задай {COMMAND_ENV}"
        )

    key = (str(Path(root).resolve()), tuple(command))
    client = _CACHE.get(key)

    if client is not None and client.alive():
        return client

    client = LspClient(command, Path(root))
    client.start()
    _CACHE[key] = client

    return client


def reset_cache() -> None:
    """Закрывает все клиенты (нужно тестам и смене настроек)."""

    for client in _CACHE.values():
        client.stop()

    _CACHE.clear()


def _relative(root: Path, path: Path) -> Path:
    """Путь относительно проекта, если он внутри."""

    resolved = (Path(root) / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()

    try:
        return resolved.relative_to(Path(root).resolve())
    except ValueError as error:
        raise LspError(f"файл вне проекта: {path}") from error


def diagnostics(root: Path, path: str) -> ToolResult:
    """Диагностика файла от языкового сервера."""

    try:
        relative = _relative(root, Path(path))
        client = client_for(root)
        items = client.diagnostics(Path(root) / relative)
    except LspError as error:
        return ToolResult(False, str(error))
    except OSError as error:
        return ToolResult(False, f"не читается файл: {error}")

    if not items:
        return ToolResult(True, f"Проблем не найдено: {relative}")

    lines = [f"Проблем: {len(items)} · {relative}"]

    for item in items:
        start = item.get("range", {}).get("start", {})
        line = int(start.get("line", 0)) + 1
        char = int(start.get("character", 0)) + 1
        level = SEVERITY.get(int(item.get("severity", 3)), "информация")
        message = str(item.get("message", "")).strip()
        code = item.get("code")

        suffix = f" [{code}]" if code else ""
        lines.append(f"{relative}:{line}:{char}: {level}: {message}{suffix}")

    return ToolResult(True, "\n".join(lines))


def definition(root: Path, path: str, line: int, character: int) -> ToolResult:
    """Переход к определению символа."""

    try:
        relative = _relative(root, Path(path))
        client = client_for(root)
        items = client.definition(Path(root) / relative, line, character)
    except LspError as error:
        return ToolResult(False, str(error))

    if not items:
        return ToolResult(True, "Определение не найдено.")

    return ToolResult(True, _format_locations(root, items))


def references(root: Path, path: str, line: int, character: int) -> ToolResult:
    """Все ссылки на символ."""

    try:
        relative = _relative(root, Path(path))
        client = client_for(root)
        items = client.references(Path(root) / relative, line, character)
    except LspError as error:
        return ToolResult(False, str(error))

    if not items:
        return ToolResult(True, "Ссылок не найдено.")

    return ToolResult(True, _format_locations(root, items))


def symbols(root: Path, path: str) -> ToolResult:
    """Список символов файла."""

    try:
        relative = _relative(root, Path(path))
        client = client_for(root)
        items = client.symbols(Path(root) / relative)
    except LspError as error:
        return ToolResult(False, str(error))

    if not items:
        return ToolResult(True, f"Символов не найдено: {relative}")

    lines = [f"Символов: {len(items)} · {relative}"]

    for item in items:
        name = str(item.get("name") or "")
        kind = SYMBOL_KINDS.get(int(item.get("kind", 0)), "символ")
        start = (item.get("range") or item.get("location", {}).get("range") or {}).get("start", {})
        line = int(start.get("line", 0)) + 1

        lines.append(f"{relative}:{line}: {kind} {name}")

    return ToolResult(True, "\n".join(lines))


def hover(root: Path, path: str, line: int, character: int) -> ToolResult:
    """Подсказка типа или документация в позиции."""

    try:
        relative = _relative(root, Path(path))
        client = client_for(root)
        result = client.hover(Path(root) / relative, line, character)
    except LspError as error:
        return ToolResult(False, str(error))

    text = _hover_text(result)

    if not text:
        return ToolResult(True, "Подсказки нет.")

    return ToolResult(True, text)


def _hover_text(result: dict) -> str:
    """Достаёт текст из ответа hover."""

    contents = result.get("contents")

    if isinstance(contents, str):
        return contents.strip()

    if isinstance(contents, dict):
        return str(contents.get("value") or "").strip()

    if isinstance(contents, list):
        parts = []

        for item in contents:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(str(item.get("value") or ""))

        return "\n".join(part for part in parts if part).strip()

    return ""


SYMBOL_KINDS = {
    1: "файл",
    2: "модуль",
    3: "пространство имён",
    4: "пакет",
    5: "класс",
    6: "метод",
    7: "свойство",
    8: "поле",
    9: "конструктор",
    10: "перечисление",
    11: "интерфейс",
    12: "функция",
    13: "переменная",
    14: "константа",
}


def _format_locations(root: Path, items: list[dict]) -> str:
    """Печатает locations в виде «файл:строка:колонка»."""

    lines = []

    for item in items:
        uri = str(item.get("uri") or item.get("targetUri") or "")
        start = item.get("range", {}).get("start") or {}
        line = int(start.get("line", 0)) + 1
        char = int(start.get("character", 0)) + 1

        path = _uri_to_path(uri, root)

        lines.append(f"{path}:{line}:{char}")

    return "\n".join(lines) or "Пусто."


def _uri_to_path(uri: str, root: Path) -> str:
    """Превращает file:// URI в путь относительно проекта."""

    if not uri.startswith("file://"):
        return uri

    raw = uri[7:]

    # Windows: file:///C:/path
    if raw.startswith("/") and len(raw) > 2 and raw[2] == ":":
        raw = raw[1:]

    try:
        from urllib.parse import unquote

        candidate = Path(unquote(raw))

        return str(candidate.relative_to(Path(root).resolve()))
    except (ValueError, OSError):
        return uri
