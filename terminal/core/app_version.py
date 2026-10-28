# Giperion/terminal/core/app_version.py                             v001
# Версия терминала и состояние установленных обновлений.
# Последнее изменение: первый вариант — точка отсчёта 1.0.0 и файл состояния.

import re
from datetime import date

from config import DATA_DIR
from shared.storage.json_store import read_json_object, update_json

# Имя продукта в окне обновления и в журнале действий.
APP_NAME = "Giperion Terminal"

# Точка отсчёта: с этой версии терминал начинает считать свои выпуски.
DEFAULT_VERSION = "1.0.0"
DEFAULT_RELEASED = "2026-10-25"

# Установленная версия переживает перезапуск (файл в .gitignore).
STATE_FILE = DATA_DIR / "update_state.json"

_VERSION_PATTERN = re.compile(r"(\d+(?:\.\d+)*)")


def version_key(text: str) -> tuple[int, ...]:
    """Превращает версию в числа, чтобы сравнивать её по частям."""

    match = _VERSION_PATTERN.search(str(text or ""))

    if match is None:
        return ()

    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(candidate: str, current: str) -> bool:
    """Проверяет, новее ли предлагаемая версия установленной."""

    left = version_key(candidate)
    right = version_key(current)

    if not left:
        return False

    length = max(len(left), len(right))
    left += (0,) * (length - len(left))
    right += (0,) * (length - len(right))

    return left > right


def read_state() -> dict:
    """Читает состояние обновлений; пустой словарь, если файла нет."""

    document = read_json_object(STATE_FILE)

    return document if isinstance(document, dict) else {}


def current_version() -> str:
    """Возвращает установленную версию терминала."""

    version = str(read_state().get("installed") or "").strip()

    return version or DEFAULT_VERSION


def current_released() -> str:
    """Возвращает дату установленного выпуска."""

    released = str(read_state().get("released") or "").strip()

    return released or DEFAULT_RELEASED


def current_patch() -> str:
    """Возвращает имя патча, которым установлена текущая версия."""

    return str(read_state().get("patch") or "").strip()


def set_installed(
    version: str,
    released: str = "",
    *,
    patch: str = "",
    note: str = "",
) -> None:
    """Запоминает установленную версию после удачного обновления."""

    def mutate(state: dict) -> dict:
        state.update(
            {
                "version": "v001",
                "app": APP_NAME,
                "installed": str(version),
                "released": str(
                    released or date.today().isoformat()
                ),
                "patch": str(patch),
                "note": str(note),
                "updated_at": date.today().isoformat(),
            }
        )

        return state

    update_json(
        STATE_FILE,
        mutate,
        default={},
        trailing_newline=True,
    )


def skipped_version() -> str:
    """Версия, которую пользователь попросил больше не предлагать."""

    return str(read_state().get("skipped") or "").strip()


def set_skipped(version: str) -> None:
    """Запоминает пропущенную версию."""

    def mutate(state: dict) -> dict:
        state["skipped"] = str(version)
        state["updated_at"] = date.today().isoformat()

        return state

    update_json(STATE_FILE, mutate, default={}, trailing_newline=True)
