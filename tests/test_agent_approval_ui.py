# Giperion/tests/test_agent_approval_ui.py                             v001
# Панель подтверждения: галочка «не спрашивать до конца задачи».

from types import SimpleNamespace

import pytest

from terminal.core.agent.protocol import ApprovalRequest


@pytest.fixture(scope="module")
def qapp():
    """Приложение Qt для окон, которым не нужен весь главный экран."""

    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def _pending(kind: str, key: str) -> ApprovalRequest:
    return ApprovalRequest(
        kind=kind,
        title="Изменить файл" if kind != "git_commit" else "Коммит",
        detail="--- a/a.txt\n+++ b/a.txt",
        path="a.txt",
        new_text="гамма",
        old_text="альфа",
        key=key,
    )


def _make_dialog(qapp):
    from terminal.ui.agent_dialog import AgentDialog

    return AgentDialog(None)


def _fake_job(pending: ApprovalRequest, captured: dict):
    return SimpleNamespace(
        steps=[],
        pending=pending,
        done=False,
        allowed=set(),
        live_tokens=0,
        live_cost=0.0,
        partial="",
        resolve_approval=lambda approved, text=None, remember=False: (
            captured.update(approved=approved, remember=remember)
        ),
    )


def test_file_approval_can_be_remembered(qapp) -> None:
    """Для файла видна галочка, и её выбор доходит до задачи."""

    dialog = _make_dialog(qapp)
    captured: dict = {}

    dialog.job = _fake_job(_pending("apply_patch", "file:a.txt"), captured)
    dialog._poll()

    assert not dialog.allow_checkbox.isHidden()
    assert dialog.allow_checkbox.text() == (
        "Больше не спрашивать этот файл"
    )
    assert dialog.allow_checkbox.isChecked() is False

    dialog.allow_checkbox.setChecked(True)
    dialog._approve()

    assert captured == {"approved": True, "remember": True}

    dialog.job = None
    dialog.close()


def test_approval_without_checkbox_sends_no_remember(qapp) -> None:
    """Без галочки разрешение остаётся разовым."""

    dialog = _make_dialog(qapp)
    captured: dict = {}

    dialog.job = _fake_job(_pending("run_command", "command:pytest -q"), captured)
    dialog._poll()

    assert dialog.allow_checkbox.text() == (
        "Больше не спрашивать эту команду"
    )
    assert dialog.allow_checkbox.isChecked() is False

    dialog._approve()

    assert captured == {"approved": True, "remember": False}

    dialog.job = None
    dialog.close()


def test_commit_has_no_remember_option(qapp) -> None:
    """Коммит нельзя разрешить оптом: галочка скрыта и не отправляется."""

    dialog = _make_dialog(qapp)
    captured: dict = {}

    dialog.job = _fake_job(_pending("git_commit", ""), captured)
    dialog._poll()

    assert dialog.allow_checkbox.isHidden()

    dialog.allow_checkbox.setChecked(True)
    dialog._approve()

    assert captured == {"approved": True, "remember": False}

    dialog.job = None
    dialog.close()


def test_template_fills_task_input(qapp) -> None:
    """Шаблон подставляет текст и возвращает список к началу."""

    dialog = _make_dialog(qapp)

    assert dialog.template_combo.count() > 1
    assert dialog.task_input.toPlainText() == ""

    dialog.template_combo.setCurrentIndex(1)

    assert dialog.task_input.toPlainText() == (
        "Найди, где объявлена функция <имя> и назови файл."
    )
    assert dialog.template_combo.currentIndex() == 0

    dialog.close()


def test_dialog_hints_unfinished_task(qapp, monkeypatch) -> None:
    """При открытии окно напоминает про незавершённую задачу."""

    from terminal.core.agent import tasks

    monkeypatch.setattr(
        tasks,
        "list_states",
        lambda limit=50: [
            {
                "id": "20261025-1",
                "task": "доделай отчёт",
                "status": tasks.STATUS_RUNNING,
            }
        ],
    )

    dialog = _make_dialog(qapp)

    assert "незавершённая" in dialog.status_label.text()
    assert "доделай отчёт" in dialog.status_label.text()

    dialog.close()


def test_task_controls_show_saved_model(qapp, monkeypatch) -> None:
    """В окне есть шаги, контекст и выбор модели; выбор восстанавливается."""

    from types import SimpleNamespace

    from terminal.ui import agent_dialog

    monkeypatch.setattr(
        agent_dialog,
        "provider_from_settings",
        lambda: SimpleNamespace(model="local-model"),
    )
    monkeypatch.setattr(
        agent_dialog,
        "_available_models",
        lambda: [
            {
                "id": "m1",
                "name": "Model One",
                "model_id": "m1",
                "provider_id": "opencode",
            }
        ],
    )
    monkeypatch.setattr(agent_dialog, "model_choice", lambda: "m1")

    dialog = agent_dialog.AgentDialog(None)

    assert 1 <= dialog.steps_input.value() <= 40
    assert 8_000 <= dialog.context_input.value() <= 2_000_000

    labels = [
        dialog.model_combo.itemText(index)
        for index in range(dialog.model_combo.count())
    ]

    assert any("Провайдер" in label for label in labels)
    assert "Model One" in labels

    current = dialog.model_combo.currentData()

    assert current["kind"] == "model"
    assert current["model"]["id"] == "m1"

    dialog.close()
