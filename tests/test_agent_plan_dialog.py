# Giperion/tests/test_agent_plan_dialog.py                             v001
# Окно плана: отображение чек-листа.

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def test_plan_dialog_shows_text(qapp) -> None:
    """Текст плана попадает в окно."""

    from PySide6.QtWidgets import QPlainTextEdit

    from terminal.ui.plan_dialog import PlanDialog

    dialog = PlanDialog(
        None,
        "1. [x] разобрать\n2. [>] проверить",
    )

    try:
        view = dialog.findChild(QPlainTextEdit)

        assert view is not None
        assert "[x] разобрать" in view.toPlainText()
    finally:
        dialog.close()
