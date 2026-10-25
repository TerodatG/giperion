# Giperion/tests/test_agent_runs_ui.py                                 v001
# Окно журнала: выбор прогона и кнопка отката файлов.

from datetime import datetime, timedelta

import pytest


@pytest.fixture(scope="module")
def qapp():
    """Приложение Qt для окон без главного экрана."""

    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def _record_with_backup(root) -> dict:
    from terminal.core.agent import tools

    target = root / "a.txt"
    target.write_text("альфа\n", encoding="utf-8")

    started = datetime.now() - timedelta(seconds=1)
    tools.apply_patch(root, "a.txt", "альфа", "гамма")

    return {
        "root": str(root),
        "files": ["a.txt"],
        "started_at": started.isoformat(timespec="seconds"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "created": "2026-10-25T19:00:00",
        "task": "правка",
        "model": "тест",
    }


def test_run_with_backup_can_be_selected(qapp, tmp_path, monkeypatch) -> None:
    """Прогон с копией появляется в списке и готов к откату."""

    from terminal.ui import agent_runs_dialog

    record = _record_with_backup(tmp_path)
    monkeypatch.setattr(
        agent_runs_dialog,
        "read_runs",
        lambda limit=60: [record],
    )

    dialog = agent_runs_dialog.AgentRunsDialog(None)

    assert dialog.run_combo.count() == 1
    assert dialog.rollback_button.isEnabled()
    assert "1 из 1" in dialog.status_label.text()

    dialog.close()


def test_run_without_files_is_not_listed(qapp, monkeypatch) -> None:
    """Записи без изменённых файлов не предлагаются для отката."""

    from terminal.ui import agent_runs_dialog

    monkeypatch.setattr(
        agent_runs_dialog,
        "read_runs",
        lambda limit=60: [{"task": "чтение", "created_at": "2026-10-25"}],
    )

    dialog = agent_runs_dialog.AgentRunsDialog(None)

    assert dialog.run_combo.count() == 0
    assert not dialog.rollback_button.isEnabled()
    assert "нет прогонов" in dialog.status_label.text().casefold()

    dialog.close()
