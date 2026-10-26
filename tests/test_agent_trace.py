# Giperion/tests/test_agent_trace.py                                  v001
# Полный трейс задачи: формат и окно.

import pytest

from terminal.core.agent.protocol import AgentStep
from terminal.ui.trace_dialog import TraceDialog, format_trace


@pytest.fixture(scope="module")
def qapp():
    """Приложение Qt для окна трейса."""

    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def test_format_trace_with_steps_and_answer() -> None:
    """Шаги, ответ и ошибка попадают в текст."""

    steps = [
        AgentStep(0, "tool", "read_file", "файл прочитан"),
        AgentStep(1, "plan", "План · 2 пунктов", "1. [ ] раз\n2. [ ] два"),
        AgentStep(2, "answer", "Ответ", "готово"),
    ]

    text = format_trace(steps, "итог", "нет")

    assert "[0] → read_file" in text
    assert "файл прочитан" in text
    assert "[1] ☑ План" in text
    assert "    1. [ ] раз" in text
    assert "ОТВЕТ:\nитог" in text
    assert "ОШИБКА:\nнет" in text


def test_format_trace_empty() -> None:
    """Пустой трейс не выглядит поломкой."""

    assert format_trace([], "", "") == "Шагов пока нет."


def test_trace_dialog_shows_text(qapp) -> None:
    """Окно трейса показывает переданный текст и только для чтения."""

    dialog = TraceDialog(None, "Трейс задачи", "строка один\nстрока два")

    assert dialog.windowTitle() == "Трейс задачи"
    assert dialog.view.isReadOnly()
    assert "строка один" in dialog.view.toPlainText()

    dialog.close()
