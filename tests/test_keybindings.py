# Giperion/tests/test_keybindings.py                                 v001
# Назначение клавиш: умолчания, хранение и конфликты.
# Последнее изменение: первый набор — каталог действий и настройки.

import pytest

from terminal.core import keybindings, window_settings


@pytest.fixture()
def settings_file(tmp_path, monkeypatch):
    """Изолирует файл настроек окна."""

    path = tmp_path / "window_settings.json"

    monkeypatch.setattr(
        window_settings,
        "WINDOW_SETTINGS_FILE",
        path,
    )

    return path


def test_defaults_cover_all_actions() -> None:
    """У каждого действия есть название и комбинация по умолчанию."""

    assert set(keybindings.DEFAULT_BINDINGS) == set(
        keybindings.ACTION_IDS
    )

    for action in keybindings.ACTIONS:
        assert action.id
        assert action.title
        assert action.default
        assert action.scope in ("window", "input")


def test_save_and_load_roundtrip(settings_file) -> None:
    """Назначения сохраняются и читаются обратно."""

    saved = keybindings.save_bindings(
        {"new_chat": "Ctrl+Shift+K"}
    )

    assert saved["new_chat"] == "Ctrl+Shift+K"
    assert saved["settings"] == keybindings.DEFAULT_BINDINGS["settings"]

    loaded = keybindings.load_bindings()

    assert loaded["new_chat"] == "Ctrl+Shift+K"
    assert loaded["settings"] == keybindings.DEFAULT_BINDINGS["settings"]


def test_unknown_actions_are_ignored(settings_file) -> None:
    """Неизвестное действие не попадает в настройки."""

    keybindings.save_bindings({"nonsense": "Ctrl+Q"})

    settings = window_settings.load_window_settings()

    assert "nonsense" not in settings["keys"]
    assert "new_chat" in settings["keys"]


def test_conflicts_are_found() -> None:
    """Одинаковые клавиши у двух действий считаются конфликтом."""

    conflicts = keybindings.find_conflicts(
        {"new_chat": "Ctrl+L", "focus_input": "ctrl+l"}
    )

    assert conflicts == [("ctrl+l", ["new_chat", "focus_input"])]

    assert keybindings.find_conflicts(
        {"new_chat": "Ctrl+N", "focus_input": "Ctrl+L"}
    ) == []


def test_empty_binding_is_allowed(settings_file) -> None:
    """Пустая комбинация сохраняется как «не задано»."""

    saved = keybindings.save_bindings({"settings": ""})

    assert saved["settings"] == ""
    assert keybindings.load_bindings()["settings"] == ""

    assert keybindings.find_conflicts(saved) == []


def test_action_titles_are_readable() -> None:
    """Название действия ищется по идентификатору."""

    assert keybindings.action_title("new_chat") == "Новый чат"
    assert keybindings.action_title("unknown") == "unknown"
