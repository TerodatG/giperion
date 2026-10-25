# Giperion/terminal/core/agent/tools_policy.py                         v001
# Границы доступа к файлам: пути, запреты и ошибки инструментов.
# Последнее изменение: вынесено из tools.

from pathlib import Path


class ToolError(RuntimeError):
    """Инструмент отказал: путь, аргумент или лимит."""


def _root(root: Path) -> Path:
    """Возвращает разрешённый корень проекта."""

    return Path(root).resolve()


def safe_path(root: Path, raw: str) -> Path:
    """Проверяет путь: только внутри проекта и без секретов."""

    base = _root(root)
    text = str(raw or ".").strip()

    if not text:
        text = "."

    candidate = Path(text)

    if not candidate.is_absolute():
        candidate = base / candidate

    resolved = candidate.resolve()

    try:
        relative = resolved.relative_to(base)
    except ValueError as error:
        raise ToolError(
            "Путь вне рабочей папки проекта запрещён."
        ) from error

    parts = relative.as_posix()

    if ".git" in relative.parts:
        raise ToolError("Служебная папка .git агенту недоступна.")

    if relative.name in DENIED_NAMES:
        raise ToolError("Этот файл закрыт для агента.")

    if relative.suffix.lower() in DENIED_SUFFIXES:
        raise ToolError("Файлы ключей закрыты для агента.")

    if parts in DENIED_RELATIVE:
        raise ToolError("Личные данные пользователя закрыты.")

    if any(
        parts == prefix or parts.startswith(prefix + "/")
        for prefix in DENIED_PREFIXES
    ):
        raise ToolError("Архивы, журналы и контексты чатов закрыты.")

    return resolved


MAX_LIST_ENTRIES = 200
MAX_READ_CHARS = 20000
MAX_READ_BYTES = 1_000_000
MAX_SEARCH_HITS = 40
MAX_SEARCH_FILE_BYTES = 512_000
MAX_SEARCH_FILES = 3000
MAX_WRITE_CHARS = 200_000
DIFF_LIMIT = 6000
TEST_TIMEOUT = 300
BACKUP_DIR = "data/agent_backups"

TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".jsonc", ".ui", ".txt", ".toml", ".cfg",
    ".ini", ".ps1", ".bat", ".cmd", ".yml", ".yaml", ".html", ".css",
    ".js", ".ts", ".csv",
}

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env", "node_modules",
    ".pytest_cache", "logs", "archive", "models", ".mypy_cache",
    ".agent_plugin_tmp",
}

DENIED_NAMES = {
    ".env", "service.json", "auth.json", "credentials.json",
    "id_rsa", "id_ed25519",
}

DENIED_SUFFIXES = (".pem", ".key", ".pfx", ".p12")

DENIED_RELATIVE = {
    "data/conversations.json",
    "data/conversations_before_model_tags.json",
    "data/user_profile.json",
}

DENIED_PREFIXES = (
    "archive",
    "logs",
    "data/chat_contexts",
)

