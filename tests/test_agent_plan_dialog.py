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


def test_plan_parse_and_cycle() -> None:
    """Пункты разбираются, статус переключается по кругу."""

    from terminal.core.agent import plan as plan_tools

    items = plan_tools.parse("1. [>] в работе\n2. [x] готово\n3. просто")

    assert [item["status"] for item in items] == [
        "doing",
        "done",
        "pending",
    ]
    assert plan_tools.cycle("pending") == "doing"
    assert plan_tools.cycle("doing") == "done"
    assert plan_tools.cycle("done") == "pending"


def test_plan_dialog_saves_edited_plan(qapp) -> None:
    """Сохранение отдаёт изменённый список наружу."""

    from terminal.ui.plan_dialog import PlanDialog

    captured = []
    dialog = PlanDialog(
        None,
        "1. [ ] старый",
        on_save=captured.append,
    )

    try:
        dialog.view.setPlainText("1. [x] новый\n2. [ ] ещё")
        dialog._save()

        assert captured
        assert [item["status"] for item in captured[0]] == [
            "done",
            "pending",
        ]
    finally:
        dialog.close()
