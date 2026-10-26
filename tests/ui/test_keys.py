# Giperion/tests/ui/test_keys.py                                     v001
# Раздел «Назначение клавиш»: перехват, сброс и применение.
# Последнее изменение: первый набор — редактор комбинаций.

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

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


def open_page(window):
    """Открывает настройки и возвращает страницу клавиш."""

    window.open_settings_dialog()

    return window.window._tool_windows["settings"].keys_panel


def press(key, modifiers=Qt.NoModifier) -> QKeyEvent:
    """Собирает событие нажатия клавиши."""

    return QKeyEvent(QEvent.KeyPress, key, modifiers)


def test_settings_has_keys_section(window, settings_file) -> None:
    """В настройках есть раздел «Клавиши» со всеми действиями."""

    window.open_settings_dialog()

    dialog = window.window._tool_windows["settings"]

    assert "КЛАВИШИ" in [b.text() for b in dialog.nav_buttons]

    page = dialog.keys_panel

    assert len(page.key_buttons) == len(keybindings.ACTIONS)
    assert page.key_buttons["settings"].text() == "Ctrl+,"
    assert page.key_buttons["new_chat"].text() == "Ctrl+N"

    dialog.close()


def test_capture_and_apply_new_shortcut(window, settings_file) -> None:
    """Новая комбинация перехватывается, применяется и сохраняется."""

    page = open_page(window)

    page._start_capture("new_chat")

    assert "Нажми" in page.key_buttons["new_chat"].text()

    page.keyPressEvent(
        press(Qt.Key_K, Qt.ControlModifier | Qt.ShiftModifier)
    )

    assert page.bindings["new_chat"] == "Ctrl+Shift+K"
    assert page.key_buttons["new_chat"].text() == "Ctrl+Shift+K"

    page._apply()

    assert "применены" in page.status_label.text()
    assert window.keybindings["new_chat"] == "Ctrl+Shift+K"
    assert keybindings.load_bindings()["new_chat"] == "Ctrl+Shift+K"

    sequences = [
        shortcut.key().toString() for shortcut in window.shortcuts
    ]

    assert "Ctrl+Shift+K" in sequences


def test_escape_and_backspace(window, settings_file) -> None:
    """Esc отменяет перехват, Backspace очищает комбинацию."""

    page = open_page(window)

    page._start_capture("agent")
    page.keyPressEvent(press(Qt.Key_Escape))

    assert page._capturing == ""
    assert page.bindings["agent"] == keybindings.DEFAULT_BINDINGS["agent"]

    page._start_capture("agent")
    page.keyPressEvent(press(Qt.Key_Backspace))

    assert page.bindings["agent"] == ""
    assert page.key_buttons["agent"].text() == "не задано"


def test_reset_single_and_all(window, settings_file) -> None:
    """Сброс возвращает значения по умолчанию."""

    page = open_page(window)

    page.bindings["new_chat"] = ""
    page._reset("new_chat")

    assert (
        page.bindings["new_chat"]
        == keybindings.DEFAULT_BINDINGS["new_chat"]
    )

    page.bindings["settings"] = ""
    page._reset_all()

    assert page.bindings == keybindings.DEFAULT_BINDINGS


def test_conflicting_keys_block_apply(window, settings_file) -> None:
    """Одинаковые клавиши не дают применить назначения."""

    page = open_page(window)

    page.bindings["new_chat"] = "Ctrl+L"
    page._apply()

    assert "повторяются" in page.status_label.text()
    assert window.keybindings["new_chat"] == "Ctrl+N"
    assert not settings_file.exists()


def test_send_binding_is_used_by_input(window, settings_file) -> None:
    """Отправка в поле ввода сверяется с назначением."""

    page = open_page(window)

    page.bindings["send"] = "Ctrl+Return"
    page._apply()

    assert window.binding_matches(
        "send",
        press(Qt.Key_Return, Qt.ControlModifier),
    )
    assert not window.binding_matches(
        "send",
        press(Qt.Key_Return),
    )
