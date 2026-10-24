# Giperion/tests/test_window_settings.py                             v005
# Проверки сохранения настроек окна, стилей и состояний модулей.
# Последнее изменение: группы шрифта трёх сенаторов.

from terminal.core.window_settings import (
    DEFAULT_MODULE_STATES,
    DEFAULT_RESPONSE_SETTINGS,
    DEFAULT_STYLES,
    load_window_settings,
    save_window_settings,
)


def test_missing_file_gives_defaults(tmp_path) -> None:
    """Без файла настроек окно получает безопасные значения."""

    settings = load_window_settings(tmp_path / "missing.json")

    assert settings["chat_font_family"] == ""
    assert settings["response"] == DEFAULT_RESPONSE_SETTINGS
    assert settings["styles"] == DEFAULT_STYLES
    assert settings["modules"] == DEFAULT_MODULE_STATES


def test_broken_font_family_falls_back_to_empty(tmp_path) -> None:
    """Некорректная гарнитура не ломает загрузку настроек."""

    path = tmp_path / "window_settings.json"
    path.write_text(
        '{"chat_font_family": "' + "x" * 200 + '"}',
        encoding="utf-8",
    )

    settings = load_window_settings(path)

    assert settings["chat_font_family"] == ""


def test_settings_roundtrip(tmp_path) -> None:
    """Сохранённые шрифт, цвета, печать и модули читаются обратно."""

    path = tmp_path / "window_settings.json"

    save_window_settings(
        {
            "chat_font_family": "Cascadia Mono",
            "chat_font_size": 18,
            "colors": {
                "bot": "#123456",
                "user": "#abcdef",
                "data": "#8fd8c8",
                "unknown": "#000000",
            },
            "styles": {
                "bot": "bold",
                "data": "italic",
                "unknown": "bold",
            },
            "response": {
                "typing_enabled": True,
                "typing_instant": True,
                "typing_speed": 70,
                "delay_enabled": True,
                "delay_seconds": 2.5,
            },
            "modules": {
                "internet": True,
                "files": False,
                "models": True,
                "voice": True,
            },
        },
        path,
    )

    settings = load_window_settings(path)

    assert settings["chat_font_family"] == "Cascadia Mono"
    assert settings["chat_font_size"] == 18
    assert settings["colors"] == {
        "bot": "#123456",
        "user": "#abcdef",
        "data": "#8fd8c8",
    }
    assert settings["styles"]["bot"] == "bold"
    assert settings["styles"]["data"] == "italic"
    assert settings["styles"]["system"] == "normal"
    assert "unknown" not in settings["styles"]
    assert settings["response"]["typing_instant"] is True
    assert settings["response"]["typing_speed"] == 70
    assert settings["response"]["delay_seconds"] == 2.5
    assert settings["modules"]["internet"] is True
    assert settings["modules"]["files"] is False


def test_invalid_values_are_clamped(tmp_path) -> None:
    """Испорченные числа не ломают окно."""

    path = tmp_path / "window_settings.json"
    path.write_text(
        '{"chat_font_size": 200, "styles": {"bot": "huge"}, '
        '"response": {"typing_speed": 999, "delay_seconds": -5}}',
        encoding="utf-8",
    )

    settings = load_window_settings(path)

    assert settings["chat_font_size"] == 28
    assert settings["styles"]["bot"] == "normal"
    assert settings["response"]["typing_speed"] == 200
    assert settings["response"]["delay_seconds"] == 0.0


def test_external_font_group_roundtrip(tmp_path) -> None:
    """Цвет, стиль и свой размер внешних моделей сохраняются."""

    path = tmp_path / "window_settings.json"

    save_window_settings(
        {
            "chat_font_size": 11,
            "colors": {"external": "#9ad7ff"},
            "styles": {"external": "bold_italic"},
            "font_sizes": {"external": 14, "bot": 0},
        },
        path,
    )

    settings = load_window_settings(path)

    assert settings["colors"]["external"] == "#9ad7ff"
    assert settings["styles"]["external"] == "bold_italic"
    assert settings["font_sizes"]["external"] == 14
    assert settings["font_sizes"]["bot"] == 0


def test_external_font_size_is_clamped(tmp_path) -> None:
    """Слишком большой или отрицательный размер группы не ломает окно."""

    path = tmp_path / "window_settings.json"
    path.write_text(
        '{"font_sizes": {"external": 900, "bot": -4}}',
        encoding="utf-8",
    )

    settings = load_window_settings(path)

    assert settings["font_sizes"]["external"] == 28
    assert settings["font_sizes"]["bot"] == 0


def test_senator_font_groups_roundtrip(tmp_path) -> None:
    """Три должности сенаторов имеют свои цвет, стиль и размер."""

    path = tmp_path / "window_settings.json"

    save_window_settings(
        {
            "chat_font_size": 11,
            "colors": {
                "senator1": "#ffd479",
                "senator2": "#e0a8ff",
                "senator3": "#7fd8b0",
            },
            "styles": {"senator2": "bold"},
            "font_sizes": {
                "senator1": 13,
                "senator2": 12,
                "senator3": 11,
            },
        },
        path,
    )

    settings = load_window_settings(path)

    assert settings["colors"]["senator1"] == "#ffd479"
    assert settings["styles"]["senator2"] == "bold"
    assert settings["font_sizes"]["senator1"] == 13
    assert settings["font_sizes"]["senator3"] == 11
