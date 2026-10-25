# Giperion/tests/test_agent_tasks_ui.py                                v001
# Окно задач агента: фильтр по статусу и список.

import pytest


@pytest.fixture(scope="module")
def qapp():
    """Приложение Qt для окон без главного экрана."""

    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


STATES = [
    {
        "id": "20261025-1",
        "task": "незавершённая",
        "status": "running",
        "updated_at": "2026-10-25T12:00:00",
    },
    {
        "id": "20261025-2",
        "task": "готовая",
        "status": "done",
        "updated_at": "2026-10-25T11:00:00",
    },
    {
        "id": "20261025-3",
        "task": "сломанная",
        "status": "error",
        "updated_at": "2026-10-25T10:00:00",
    },
]


@pytest.fixture()
def dialog(qapp, monkeypatch):
    from terminal.ui import agent_tasks_dialog

    monkeypatch.setattr(
        agent_tasks_dialog,
        "list_states",
        lambda limit=50: [dict(state) for state in STATES],
    )

    window = agent_tasks_dialog.AgentTasksDialog(None)

    yield window

    window.close()


def _titles(dialog) -> list[str]:
    return [
        dialog.view.item(row).text().splitlines()[0]
        for row in range(dialog.view.count())
    ]


def test_filter_shows_all_by_default(dialog) -> None:
    """Без фильтра видно все задачи."""

    assert dialog.view.count() == 3
    assert _titles(dialog) == [
        "незавершённая",
        "готовая",
        "сломанная",
    ]


def test_filter_by_running_status(dialog) -> None:
    """Фильтр «Незавершённые» оставляет только running."""

    index = dialog.filter_combo.findData("running")
    dialog.filter_combo.setCurrentIndex(index)

    assert dialog.view.count() == 1
    assert _titles(dialog) == ["незавершённая"]

    dialog.view.setCurrentRow(0)

    assert dialog.resume_button.isEnabled()
    assert dialog.remove_button.isEnabled()


def test_filter_by_error_status(dialog) -> None:
    """Фильтр «С ошибкой» оставляет упавшие задачи."""

    dialog.filter_combo.setCurrentIndex(
        dialog.filter_combo.findData("error")
    )

    assert _titles(dialog) == ["сломанная"]


def test_empty_filter_shows_hint(dialog) -> None:
    """Если под фильтр ничего не подошло, об этом сказано."""

    dialog.filter_combo.setCurrentIndex(
        dialog.filter_combo.findData("cancelled")
    )

    assert dialog.view.count() == 0
    assert "не подходят" in dialog.details.text()
