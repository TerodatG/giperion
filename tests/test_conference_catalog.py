# Giperion/tests/test_conference_catalog.py                        v001
# Проверки трёх режимов конференции и выбранного режима.

from terminal.core import conference_catalog


def test_three_modes_are_available() -> None:
    """Подготовлены совет, дебаты и модератор."""

    mode_ids = [mode["id"] for mode in conference_catalog.CONFERENCE_MODES]

    assert mode_ids == ["council", "debate", "moderator"]
    assert all(
        mode["name"] and mode["summary"]
        for mode in conference_catalog.CONFERENCE_MODES
    )


def test_selected_mode_is_saved(tmp_path, monkeypatch) -> None:
    """Выбранный режим запоминается в отдельном файле."""

    monkeypatch.setattr(
        conference_catalog,
        "CONFERENCE_SETTINGS_FILE",
        tmp_path / "conference_settings.json",
    )

    assert (
        conference_catalog.get_selected_mode_id()
        == "council"
    )
    assert conference_catalog.set_selected_mode_id("moderator") is True
    assert (
        conference_catalog.get_selected_mode_id()
        == "moderator"
    )
    assert conference_catalog.set_selected_mode_id("unknown") is False
