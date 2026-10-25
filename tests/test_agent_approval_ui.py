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
