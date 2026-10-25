# Giperion/terminal/ui/agent_tasks_dialog.py                         v001
# Окно «Задачи агента»: сохранённые задачи и продолжение.
# Последнее изменение: первый вариант — список, детали, resume.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from terminal.core.agent.tasks import (
    list_states,
    remove_state,
)
from terminal.ui.dialogs_base import SkinDialog, show_tool_window

STATUS_TITLES = {
    "running": "не завершена",
    "done": "готова",
    "error": "ошибка",
    "cancelled": "остановлена",
}


class AgentTasksDialog(SkinDialog):
    """Список сохранённых задач агента."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Задачи агента",
            min_width=860,
            min_height=580,
        )

        self._parent = parent
        self._states: list[dict] = []

        self._build()
        self._refresh()

    def _build(self) -> None:
        title = QLabel("ЗАДАЧИ АГЕНТА", self)
        title.setObjectName("dialogTitle")

        hint = QLabel(
            "Сохранённые задачи: можно продолжить с историей шагов "
            "или удалить. Незавершённые задачи остаются здесь после "
            "закрытия окна или перезапуска.",
            self,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        body = QHBoxLayout()
        body.setSpacing(10)

        self.view = QListWidget(self)
        self.view.setObjectName("modelsView")
        self.view.setSelectionMode(QListWidget.SingleSelection)
        self.view.currentItemChanged.connect(
            lambda current, previous: self._show_details()
        )

        details_frame = QWidget(self)
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(8, 4, 4, 4)
        details_layout.setSpacing(6)

        self.details = QLabel("Выбери задачу слева.", details_frame)
        self.details.setObjectName("dialogHint")
        self.details.setWordWrap(True)
        self.details.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        details_layout.addWidget(self.details, 1)

        body.addWidget(self.view, 1)
        body.addWidget(details_frame, 1)

        self.resume_button = QPushButton("Продолжить", self)
        self.resume_button.setObjectName("workshopAction")
        self.resume_button.setEnabled(False)
        self.resume_button.clicked.connect(self._resume)

        self.remove_button = QPushButton("Удалить", self)
        self.remove_button.setObjectName("workshopAction")
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self._remove)

        self.refresh_button = QPushButton("Обновить", self)
        self.refresh_button.setObjectName("workshopAction")
        self.refresh_button.clicked.connect(self._refresh)

        self.filter_combo = QComboBox(self)
        self.filter_combo.setObjectName("approvalPolicy")
        self.filter_combo.addItem("Все задачи", "")
        self.filter_combo.addItem("Незавершённые", "running")
        self.filter_combo.addItem("Готовые", "done")
        self.filter_combo.addItem("С ошибкой", "error")
        self.filter_combo.addItem("Остановленные", "cancelled")
        self.filter_combo.currentIndexChanged.connect(self._refresh)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.filter_combo)
        row.addWidget(self.resume_button)
        row.addWidget(self.remove_button)
        row.addWidget(self.refresh_button)
        row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(hint)
        self.body_layout.addLayout(body, 1)
        self.body_layout.addLayout(row)
        self.body_layout.addWidget(buttons)

    def _refresh(self) -> None:
        status_filter = ""

        if hasattr(self, "filter_combo"):
            status_filter = str(
                self.filter_combo.currentData() or ""
            )

        states = list_states()
        self._states = [
            state
            for state in states
            if not status_filter
            or str(state.get("status")) == status_filter
        ]
        self.view.clear()

        for state in self._states:
            status = STATUS_TITLES.get(
                str(state.get("status")),
                str(state.get("status")),
            )
            task = str(state.get("task") or "").splitlines()
            title = task[0][:70] if task else "без описания"

            item = QListWidgetItem(
                f"{title}\n{status} · {state.get('updated_at', '')}"
            )
            item.setData(Qt.UserRole, state.get("id"))
            self.view.addItem(item)

        self.resume_button.setEnabled(False)
        self.remove_button.setEnabled(False)

        if not self._states:
            if states:
                self.details.setText(
                    "Под этот фильтр задачи не подходят."
                )
            else:
                self.details.setText(
                    "Сохранённых задач нет. Запусти агента — задача "
                    "появится здесь."
                )

    def _selected(self) -> dict | None:
        item = self.view.currentItem()

        if item is None:
            return None

        task_id = item.data(Qt.UserRole)

        for state in self._states:
            if state.get("id") == task_id:
                return state

        return None

    def _show_details(self) -> None:
        state = self._selected()

        if state is None:
            self.details.setText("Выбери задачу слева.")
            self.resume_button.setEnabled(False)
            self.remove_button.setEnabled(False)

            return

        steps = state.get("steps") or []
        history = state.get("history") or []
        answer = str(state.get("answer") or "").strip()
        error = str(state.get("error") or "").strip()

        lines = [
            f"Задача: {state.get('task', '')}",
            f"Модель: {state.get('model', '—')}",
            f"Политика: {state.get('policy', '—')}",
            f"Папка: {state.get('root', '—')}",
            f"Шагов: {len(steps)} · вызовов: {len(history)}",
        ]

        if state.get("worktree_branch"):
            lines.append(
                "Ветка: " + str(state["worktree_branch"])
            )

        if answer:
            lines.append("Ответ: " + answer[:300])

        if error:
            lines.append("Ошибка: " + error[:300])

        self.details.setText("\n\n".join(lines))
        self.resume_button.setEnabled(True)
        self.remove_button.setEnabled(True)

    def _resume(self) -> None:
        state = self._selected()

        if state is None:
            return

        task_id = str(state.get("id") or "")
        self.accept()

        from terminal.ui.agent_dialog import show_agent_dialog

        show_agent_dialog(
            self._parent,
            f"agent-resume-{task_id}",
            resume=state,
        )

    def _remove(self) -> None:
        state = self._selected()

        if state is None:
            return

        remove_state(str(state.get("id") or ""))
        self._refresh()


def show_agent_tasks_dialog(parent) -> None:
    """Открывает немодальный список задач агента."""

    dialog = AgentTasksDialog(parent)
    show_tool_window(parent, dialog, "agent-tasks")
