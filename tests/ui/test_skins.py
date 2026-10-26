# Giperion/tests/ui/test_skins.py                                    v001
# Раздел «Скины» в настройках: список, предпросмотр и применение.
# Последнее изменение: первый набор — страница и применение.

from dataclasses import replace

import pytest

from terminal.core import skins, window_settings


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


def find_row(page, skin_id: str) -> int:
    """Номер строки скина в списке."""

    from PySide6.QtCore import Qt

    for row in range(page.skin_list.count()):
        if page.skin_list.item(row).data(Qt.UserRole) == skin_id:
            return row

    return -1


def test_settings_has_skins_section(window, settings_file) -> None:
    """В настройках есть раздел «Скины» с миниатюрой окна."""

    window.open_settings_dialog()

    dialog = window.window._tool_windows["settings"]

    titles = [button.text() for button in dialog.nav_buttons]

    assert "СКИНЫ" in titles

    page = dialog.skins_panel

    assert page.skin_list.count() == len(skins.SKINS)
    assert page.preview.skin.id == "terminal"

    pixmap = page.preview.grab()

    assert not pixmap.isNull()
    assert pixmap.width() > 100

    dialog.close()


def test_draft_skin_shows_preview_but_not_applied(
    window,
    settings_file,
) -> None:
    """«Убежище» показывает предпросмотр, но применить его нельзя."""

    window.open_settings_dialog()

    dialog = window.window._tool_windows["settings"]
    page = dialog.skins_panel

    row = find_row(page, "vault")
    page.skin_list.setCurrentRow(row)

    assert page.selected_id == "vault"
    assert page.preview.skin.id == "vault"
    assert page.apply_button.isEnabled() is False
    assert "Готовится" in page.status_label.text()

    dialog.close()


def test_current_skin_cannot_be_applied_again(
    window,
    settings_file,
) -> None:
    """Активный скин не применяется повторно."""

    window.open_settings_dialog()

    dialog = window.window._tool_windows["settings"]
    page = dialog.skins_panel

    page.skin_list.setCurrentRow(find_row(page, "terminal"))

    assert page.apply_button.isEnabled() is False
    assert "уже активен" in page.status_label.text()

    dialog.close()


def test_apply_button_switches_skin(
    window,
    settings_file,
    monkeypatch,
) -> None:
    """Кнопка «Применить» переключает готовый скин и сохраняет выбор."""

    from terminal.ui import settings_skins

    extra = replace(
        skins.get_skin("terminal"),
        id="terminal-copy",
        name="Копия",
        status="ready",
    )
    catalog = skins.SKINS + (extra,)

    monkeypatch.setattr(skins, "SKINS", catalog)
    monkeypatch.setattr(
        skins,
        "SKIN_IDS",
        tuple(skin.id for skin in catalog),
    )
    monkeypatch.setattr(settings_skins, "SKINS", catalog)

    window.open_settings_dialog()

    dialog = window.window._tool_windows["settings"]
    page = dialog.skins_panel

    page.skin_list.setCurrentRow(find_row(page, "terminal-copy"))

    assert page.apply_button.isEnabled() is True

    page.apply_button.click()

    assert window.skin_id == "terminal-copy"
    assert skins.load_skin_id() == "terminal-copy"
    assert page.current_id == "terminal-copy"
    assert "применён" in page.status_label.text()

    dialog.close()
