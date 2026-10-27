# Giperion/terminal/core/agent/onboarding.py                          v001
# Флаг онбординга в настройках агента.
# Последнее изменение: вынесено из settings, чтобы не раздувать модуль.

from shared.storage.json_store import read_json_object, update_json
from terminal.core.agent.settings import SETTINGS_FILE


def done() -> bool:
    """Показывался ли онбординг."""

    return read_json_object(SETTINGS_FILE).get("onboarding_done") is True


def set_done(value: bool = True) -> None:
    """Запоминает, что онбординг показан."""

    def mutate(document: dict) -> dict:
        document["onboarding_done"] = bool(value)

        return document

    update_json(SETTINGS_FILE, mutate, default={})
