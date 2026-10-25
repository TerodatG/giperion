# Giperion/terminal/core/agent/settings.py                           v001
# Настройки провайдера агента и выбор источника: файл или окружение.
# Последнее изменение: первый вариант — base_url, ключ и модель.

import os
from pathlib import Path

from config import DATA_DIR
from shared.storage.json_store import read_json_object, write_json

SETTINGS_FILE = DATA_DIR / "agent_settings.json"

EMPTY = {
    "base_url": "",
    "api_key": "",
    "model": "",
}


def load_settings() -> dict[str, str]:
    """Читает настройки провайдера; битые поля заменяются пустыми."""

    document = read_json_object(SETTINGS_FILE)
    result = dict(EMPTY)

    for key in EMPTY:
        value = document.get(key)

        if isinstance(value, str):
            result[key] = value.strip()

    return result


def save_settings(
    base_url: str,
    api_key: str,
    model: str,
) -> dict[str, str]:
    """Сохраняет настройки провайдера в gitignored-файл."""

    values = {
        "base_url": str(base_url or "").strip(),
        "api_key": str(api_key or "").strip(),
        "model": str(model or "").strip(),
    }

    document = read_json_object(SETTINGS_FILE)
    document.update(values)
    write_json(SETTINGS_FILE, document)

    return values


def has_settings(values: dict[str, str] | None = None) -> bool:
    """Заполнены ли все три поля провайдера."""

    data = values if values is not None else load_settings()

    return all(bool(data.get(key)) for key in EMPTY)


def mask_key(key: str) -> str:
    """Прячет ключ, оставляя последние четыре символа."""

    text = str(key or "")

    if len(text) <= 4:
        return "•" * len(text)

    return "•" * (len(text) - 4) + text[-4:]


def env_provider_values() -> dict[str, str]:
    """Значения провайдера из переменных окружения."""

    return {
        "base_url": os.environ.get("AGENT_BASE_URL", "").strip(),
        "api_key": os.environ.get("AGENT_API_KEY", "").strip(),
        "model": os.environ.get("AGENT_MODEL", "").strip(),
    }


def resolve_provider_values() -> dict[str, str]:
    """Настройки из файла важнее окружения; иначе окружение."""

    stored = load_settings()

    if has_settings(stored):
        return stored

    return env_provider_values()


def provider_from_settings():
    """Собирает провайдера из файла/окружения или возвращает None."""

    from terminal.core.agent.providers import (
        OpenAICompatibleProvider,
    )

    values = resolve_provider_values()

    if not has_settings(values):
        return None

    return OpenAICompatibleProvider(
        values["base_url"],
        values["api_key"],
        values["model"],
    )


def settings_file() -> Path:
    """Путь к файлу настроек агента."""

    return SETTINGS_FILE
