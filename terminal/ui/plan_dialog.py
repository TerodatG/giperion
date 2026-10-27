# Giperion/terminal/ui/plan_dialog.py                                  v002
# Окно плана задачи: редактируемый чек-лист и ручные статусы.
# Последнее изменение: добавление, удаление, смена статуса и сохранение.

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from terminal.core.agent import plan as plan_tools
from terminal.core.agent.loop_helpers import render_plan
from terminal.ui.dialogs_base import SkinDialog, show_tool_window

MARKS = {"pending": "[ ]", "doing": "[>]", "done": "[x]"}


class PlanDialog(SkinDialog):
    """Редактирует чек-лист задачи и отдаёт его в цикл."""

    def __init__(
        self,
        parent,
        plan,
        title: str = "План задачи",
        on_save=None,
    ) -> None:
        super().__init__(
            parent,
            title,
            min_width=620,
            min_height=440,
        )
        self.on_save = on_save
        self.plan = plan_tools.parse(plan) if isinstance(plan, str) else list(plan or [])
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Чек-лист можно править: [ ] — не начато, [>] — в работе, "
            "[x] — готово. Сохранение передаёт план агенту на следующем "
            "шаге.",
            self,
        )
        hint.setWordWrap(True)
        hint.setObjectName("dialogHint")
        layout.addWidget(hint)

        self.view = QPlainTextEdit(self)
        self.view.setPlainText(render_plan(self.plan))
        layout.addWidget(self.view, 1)

        self.status = QLabel("", self)
        self.status.setObjectName("dialogHint")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        add = QPushButton("Добавить", self)
        add.clicked.connect(self._add)
        remove = QPushButton("Удалить", self)
        remove.clicked.connect(self._remove)
        toggle = QPushButton("Статус", self)
        toggle.clicked.connect(self._toggle)
        save = QPushButton("Сохранить", self)
        save.clicked.connect(self._save)
        close = QPushButton("Закрыть", self)
        close.clicked.connect(self.close)
        row.addWidget(add)
        row.addWidget(remove)
        row.addWidget(toggle)
        row.addWidget(save)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)

    def _lines(self) -> list[str]:
        return self.view.toPlainText().splitlines()

    def _add(self) -> None:
        """Добавляет пункт в конец."""

        text = self.view.toPlainText().rstrip()
        self.view.setPlainText(
            (text + "\n" if text else "")
            + f"{len(self._lines()) + 1}. [ ] новый пункт"
        )
        self.view.setFocus()

    def _remove(self) -> None:
        """Удаляет строку под курсором."""

        cursor = self.view.textCursor()
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        cursor.removeSelectedText()
        cursor.deleteChar()
        self.view.setTextCursor(cursor)

    def _toggle(self) -> None:
        """Меняет статус строки под курсором."""

        cursor = self.view.textCursor()
        block = cursor.block()
        line = block.text()
        items = plan_tools.parse(line)

        if not items:
            return

        item = items[0]
        status = plan_tools.cycle(str(item.get("status") or "pending"))
        replacement = (
            f"{block.blockNumber() + 1}. {MARKS[status]} {item['text']}"
        )
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        cursor.insertText(replacement)

    def _save(self) -> None:
        """Разбирает текст и передаёт план наружу."""

        self.plan = plan_tools.parse(self.view.toPlainText())

        if self.on_save is not None:
            self.on_save(self.plan)

        self.status.setText(
            f"Сохранено пунктов: {len(self.plan)}."
        )


def show_plan_dialog(
    parent,
    plan,
    title: str = "План задачи",
    on_save=None,
) -> None:
    """Открывает редактируемый план немодальным окном."""

    dialog = PlanDialog(parent, plan, title, on_save)
    show_tool_window(parent, dialog, "agent-plan")
