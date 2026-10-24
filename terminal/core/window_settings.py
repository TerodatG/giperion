# Giperion/app/core/window_settings.py                             v007
# Настройки окна: шрифт, цвета, стили текста, печать и модули.
# Последнее изменение: группы шрифта трёх сенаторов.

import copy
from pathlib import Path

from shared.storage.json_store import read_json, write_json
from config import DATA_DIR

WINDOW_SETTINGS_FILE = DATA_DIR / "window_settings.json"

# Цвета и стили, которые разрешено менять в окне «Вид».
# «data» — текст, прочитанный из файла или найденный в интернете.
# «external» — ответы внешних моделей: своя группа цвета и размера.
COLOR_KEYS = (
    "system",
    "bot",
    "external",
    "senator1",
    "senator2",
    "senator3",
    "user",
    "message",
    "data",
)
STYLE_KEYS = COLOR_KEYS

# Вид шрифта для группы текста.
STYLE_VALUES = ("normal", "bold", "italic", "bold_italic")

DEFAULT_STYLES = {
    "system": "normal",
    "bot": "normal",
    "external": "normal",
    "senator1": "normal",
    "senator2": "normal",
    "senator3": "normal",
    "user": "normal",
    "message": "normal",
    "data": "normal",
}

# Свой размер шрифта для группы. 0 — наследовать общий размер чата.
DEFAULT_FONT_SIZES = {key: 0 for key in COLOR_KEYS}

# Настройки вывода ответа по умолчанию.
DEFAULT_RESPONSE_SETTINGS = {
    "typing_enabled": True,
    "typing_instant": False,
    "typing_speed": 35,
    "delay_enabled": False,
    "delay_seconds": 1.0,
}

# Модули панели: что разрешено ИИ.
DEFAULT_MODULE_STATES = {
    "internet": False,
    "files": True,
    "models": False,
    "conference": False,
    "voice": False,
}

DEFAULT_WINDOW_SETTINGS = {
    "chat_font_family": "",
    "chat_font_size": 11,
    "colors": {},
    "styles": DEFAULT_STYLES,
    "font_sizes": DEFAULT_FONT_SIZES,
    "response": DEFAULT_RESPONSE_SETTINGS,
    "modules": DEFAULT_MODULE_STATES,
}


def _clean_font_family(value: object) -> str:
    """Проверяет название гарнитуры шрифта."""

    if not isinstance(value, str):
        return ""

    family = value.strip()

    if len(family) > 120:
        return ""

    return family


def _clean_response(value: object) -> dict:
    """Проверяет сохранённые настройки печати и задержки."""

    settings = dict(DEFAULT_RESPONSE_SETTINGS)

    if not isinstance(value, dict):
        return settings

    for key in ("typing_enabled", "typing_instant", "delay_enabled"):
        if isinstance(value.get(key), bool):
            settings[key] = value[key]

    speed = value.get("typing_speed")

    if isinstance(speed, (int, float)):
        settings["typing_speed"] = max(5, min(200, int(speed)))

    delay = value.get("delay_seconds")

    if isinstance(delay, (int, float)):
        settings["delay_seconds"] = max(
            0.0,
            min(10.0, round(float(delay), 1)),
        )

    return settings


def _clean_styles(value: object) -> dict:
    """Проверяет стили групп текста и дополняет недостающие."""

    styles = dict(DEFAULT_STYLES)

    if not isinstance(value, dict):
        return styles

    for key in STYLE_KEYS:
        style = value.get(key)

        if style in STYLE_VALUES:
            styles[key] = style

    return styles


def _clean_font_sizes(value: object) -> dict:
    """Проверяет размеры шрифта групп текста."""

    sizes = dict(DEFAULT_FONT_SIZES)

    if not isinstance(value, dict):
        return sizes

    for key in DEFAULT_FONT_SIZES:
        size = value.get(key)

        if isinstance(size, int) and not isinstance(size, bool):
            sizes[key] = max(0, min(28, size))

    return sizes


def _clean_modules(value: object) -> dict:
    """Проверяет сохранённые состояния модулей."""

    settings = dict(DEFAULT_MODULE_STATES)

    if not isinstance(value, dict):
        return settings

    for key in DEFAULT_MODULE_STATES:
        if isinstance(value.get(key), bool):
            settings[key] = value[key]

    return settings


def load_window_settings(
    path: Path | None = None,
) -> dict:
    """Загружает настройки окна и добавляет недостающие поля."""

    file_path = path or WINDOW_SETTINGS_FILE
    document = read_json(file_path, {})

    if not isinstance(document, dict):
        document = {}

    settings = copy.deepcopy(DEFAULT_WINDOW_SETTINGS)

    settings["chat_font_family"] = _clean_font_family(
        document.get("chat_font_family")
    )

    font_size = document.get("chat_font_size")

    if isinstance(font_size, int):
        settings["chat_font_size"] = max(8, min(28, font_size))

    colors = document.get("colors")

    if isinstance(colors, dict):
        settings["colors"] = {
            key: value
            for key, value in colors.items()
            if key in COLOR_KEYS and isinstance(value, str)
        }

    settings["styles"] = _clean_styles(
        document.get("styles")
    )
    settings["font_sizes"] = _clean_font_sizes(
        document.get("font_sizes")
    )
    settings["response"] = _clean_response(
        document.get("response")
    )
    settings["modules"] = _clean_modules(
        document.get("modules")
    )

    return settings


def save_window_settings(
    settings: dict,
    path: Path | None = None,
) -> None:
    """Сохраняет только известные и проверенные поля настроек."""

    file_path = path or WINDOW_SETTINGS_FILE

    document = {
        "chat_font_family": _clean_font_family(
            settings.get("chat_font_family")
        ),
        "chat_font_size": max(
            8,
            min(
                28,
                int(
                    settings.get(
                        "chat_font_size",
                        DEFAULT_WINDOW_SETTINGS["chat_font_size"],
                    )
                ),
            ),
        ),
        "colors": {
            key: value
            for key, value in dict(
                settings.get("colors", {})
            ).items()
            if key in COLOR_KEYS and isinstance(value, str)
        },
        "styles": _clean_styles(
            settings.get("styles")
        ),
        "font_sizes": _clean_font_sizes(
            settings.get("font_sizes")
        ),
        "response": _clean_response(
            settings.get("response")
        ),
        "modules": _clean_modules(
            settings.get("modules")
        ),
    }

    write_json(file_path, document)
