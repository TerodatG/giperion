# Giperion/terminal/core/agent/browser_profile.py                     v001
# Профиль браузера: cookies и localStorage между задачами.
# Последнее изменение: первый вариант — storage_state в data/agent_browser.

from config import DATA_DIR

PROFILE_FILE = DATA_DIR / "agent_browser" / "profile.json"


def load_state() -> str:
    """Путь к сохранённому профилю или пустая строка."""

    return str(PROFILE_FILE) if PROFILE_FILE.is_file() else ""


def save_profile(context) -> None:
    """Сохраняет cookies и localStorage для следующей задачи."""

    if context is None:
        return

    try:
        PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(PROFILE_FILE))
    except Exception:  # noqa: BLE001 — профиль не должен ломать ответ
        pass
