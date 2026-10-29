# Giperion/terminal/api/config.py                                      v001
# Параметры HTTP-API: адрес, токен, разрешённые проекты и лимиты.

import os
import secrets
from pathlib import Path

from config import BASE_DIR, DATA_DIR

# Адрес по умолчанию — только локальная петля.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8777

HOST_ENV = "GIPERION_API_HOST"
PORT_ENV = "GIPERION_API_PORT"
TOKEN_ENV = "GIPERION_API_TOKEN"
ROOTS_ENV = "GIPERION_API_ROOTS"

TOKEN_FILE = DATA_DIR / "api_token.txt"

# Ограничения, чтобы один вызов не съел память и время.
MAX_TASK_CHARS = 8000
MAX_BODY_BYTES = 64 * 1024
MAX_STEPS = 40
DEFAULT_STEPS = 12


class ApiConfigError(RuntimeError):
    """Понятная ошибка параметров API."""


def api_host() -> str:
    """Адрес, который слушает сервер."""

    return os.environ.get(HOST_ENV, "").strip() or DEFAULT_HOST


def api_port() -> int:
    """Порт сервера."""

    raw = os.environ.get(PORT_ENV, "").strip()

    if not raw:
        return DEFAULT_PORT

    try:
        port = int(raw)
    except ValueError as error:
        raise ApiConfigError(f"порт должен быть числом: {raw}") from error

    if not 1 <= port <= 65535:
        raise ApiConfigError(f"порт вне диапазона: {port}")

    return port


def api_token(create: bool = True) -> str:
    """Токен доступа: переменная окружения или файл в data/."""

    override = os.environ.get(TOKEN_ENV, "").strip()

    if override:
        return override

    if TOKEN_FILE.is_file():
        stored = TOKEN_FILE.read_text(encoding="utf-8").strip()

        if stored:
            return stored

    if not create:
        return ""

    token = secrets.token_urlsafe(32)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token + "\n", encoding="utf-8")

    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass

    return token


def allowed_roots() -> tuple[Path, ...]:
    """Каталоги, в которых API может запускать задачи."""

    raw = os.environ.get(ROOTS_ENV, "").strip()

    if not raw:
        return (Path(BASE_DIR).resolve(),)

    roots = []

    for item in raw.split(os.pathsep):
        item = item.strip()

        if item:
            roots.append(Path(item).expanduser().resolve())

    return tuple(roots) or (Path(BASE_DIR).resolve(),)


def resolve_project(project: str) -> Path:
    """Проверяет, что проект существует и разрешён."""

    candidate = Path(project or ".").expanduser()

    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ApiConfigError(f"проект не найден: {project}") from error

    if not resolved.is_dir():
        raise ApiConfigError(f"проект не каталог: {project}")

    for root in allowed_roots():
        if resolved == root or root in resolved.parents:
            return resolved

    raise ApiConfigError(
        f"проект вне разрешённых каталогов: {resolved}"
    )
