# Giperion/terminal/ui/agent/trace.py                                 v001
# Лента шагов агента: знак, номер, заголовок и подробность.
# Последнее изменение: вынесено из agent_dialog.

from PySide6.QtWidgets import QPlainTextEdit

from terminal.ui.agent.constants import STEP_MARKS


class AgentTrace(QPlainTextEdit):
    """Read-only лента событий задачи."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setObjectName("agentTrace")
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)

    def append_step(self, step) -> None:
        """Добавляет один шаг в ленту."""

        mark = STEP_MARKS.get(step.kind, "·")
        lines = [f"[{step.index}] {mark} {step.title}"]

        if step.detail:
            lines.append("    " + step.detail)

        self.appendPlainText("\n".join(lines))
