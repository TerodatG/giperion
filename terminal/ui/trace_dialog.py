# Giperion/terminal/ui/trace_dialog.py                                  v001
# Окно с полным трейсом задачи: шаги, ответ, ошибка.
# Последнее изменение: первый вариант — отдельное окно и формат текста.

from PySide6.QtWidgets import (
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
)

from terminal.ui.dialogs_base import SkinDialog, show_tool_window

STEP_MARKS = {
    "tool": "→",
    "answer": "✓",
    "error": "!",
    "approval": "▣",
    "subagent": "↳",
    "secret": "▤",
    "budget": "Σ",
    "security": "⚠",
    "plan": "☑",
}


def format_trace(steps, answer: str = "", error: str = "") -> str:
    """Собирает шаги задачи в читаемый текст."""

    lines = []

    for step in steps or []:
        mark = STEP_MARKS.get(getattr(step, "kind", ""), "·")
        lines.append(
            f"[{getattr(step, 'index', 0)}] {mark} "
            f"{getattr(step, 'title', '')}"
        )

        detail = str(getattr(step, "detail", "") or "")

        if detail:
            for line in detail.splitlines():
                lines.append("    " + line)

        lines.append("")

    if answer:
        lines.append("ОТВЕТ:")
        lines.append(str(answer))

    if error:
        lines.append("")
        lines.append("ОШИБКА:")
        lines.append(str(error))

    return "\n".join(lines).strip() or "Шагов пока нет."


class TraceDialog(SkinDialog):
    """Полный трейс одной задачи."""

    def __init__(self, parent, title: str, text: str) -> None:
        super().__init__(
            parent,
            title,
            min_width=820,
            min_height=560,
        )

        header = QLabel(title.upper(), self)
        header.setObjectName("dialogTitle")

        self.view = QPlainTextEdit(self)
        self.view.setObjectName("agentTrace")
        self.view.setReadOnly(True)
        self.view.setPlainText(text)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)

        self.body_layout.addWidget(header)
        self.body_layout.addWidget(self.view, 1)
        self.body_layout.addWidget(buttons)


def show_trace_dialog(
    parent,
    title: str,
    text: str,
    key: str = "agent-trace",
) -> None:
    """Открывает немодальное окно трейса."""

    dialog = TraceDialog(parent, title, text)
    show_tool_window(parent, dialog, key)
