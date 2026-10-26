# Giperion/terminal/ui/plan_dialog.py                                  v001
# Окно плана задачи: чек-лист из шагов update_plan.
# Последнее изменение: первый вариант — текст плана в отдельном окне.

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QVBoxLayout

from terminal.ui.dialogs_base import SkinDialog, show_tool_window


class PlanDialog(SkinDialog):
    """Показывает последний чек-лист задачи."""

    def __init__(self, parent, text: str, title: str = "План задачи") -> None:
        super().__init__(
            parent,
            title,
            min_width=560,
            min_height=360,
        )

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Чек-лист, который модель ведёт через update_plan: "
            "[ ] — не начато, [>] — в работе, [x] — готово.",
            self,
        )
        hint.setWordWrap(True)
        hint.setObjectName("dialogHint")
        layout.addWidget(hint)

        view = QPlainTextEdit(self)
        view.setReadOnly(True)
        view.setPlainText(str(text or "План пока не составлен."))
        layout.addWidget(view, 1)


def show_plan_dialog(parent, text: str, title: str = "План задачи") -> None:
    """Открывает план немодальным окном."""

    dialog = PlanDialog(parent, text, title)
    show_tool_window(parent, dialog, "agent-plan")
