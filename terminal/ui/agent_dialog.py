# Giperion/terminal/ui/agent_dialog.py                               v002
# Окно «Агент»: задача, лента шагов, подтверждения и worktree.
# Последнее изменение: отдельная ветка и параллельные задачи.

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import BASE_DIR
from terminal.core.agent.brain import ModelBrain
from terminal.core.agent.worktrees import (
    WorktreeError,
    create_worktree,
)
from terminal.core.helper_model import get_helper_model
from terminal.core.model_registry import (
    DEFAULT_MODEL_ID,
    get_active_model,
)
from terminal.ui.agent_job import AgentJob
from terminal.ui.dialogs_base import SkinDialog, show_tool_window

MAX_STEPS = 12
POLL_MS = 120

STEP_MARKS = {
    "tool": "→",
    "answer": "✓",
    "error": "!",
    "approval": "▣",
    "subagent": "↳",
}


def _pick_model() -> dict | None:
    """Берёт активную внешнюю модель или лучшего помощника."""

    active = get_active_model()

    if (
        active is not None
        and active["id"] != DEFAULT_MODEL_ID
        and active.get("model_id")
    ):
        return active

    return get_helper_model()


class AgentDialog(SkinDialog):
    """Окно агента; при закрытии останавливает текущую задачу."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Агент",
            min_width=900,
            min_height=640,
        )

        self.job: AgentJob | None = None
        self._shown = 0
        self._editing = False
        self._parent = parent
        self.worktree_path: Path | None = None
        self.worktree_branch = ""

        self._build()
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

    def _build(self) -> None:
        """Собирает поля, кнопки и ленту шагов."""

        title = QLabel("АГЕНТ", self)
        title.setObjectName("dialogTitle")

        subtitle = QLabel(
            "Задача по проекту: агент ищет и читает файлы, затем "
            "отвечает со ссылками. Запись и команды пока запрещены. "
            "Прочитанные файлы уходят провайдеру выбранной модели.",
            self,
        )
        subtitle.setObjectName("dialogHint")
        subtitle.setWordWrap(True)

        self.task_input = QPlainTextEdit(self)
        self.task_input.setObjectName("agentTask")
        self.task_input.setPlaceholderText(
            "Например: как устроена граница модели и агента?"
        )
        self.task_input.setFixedHeight(64)

        self.worktree_checkbox = QCheckBox(
            "Отдельная ветка (worktree)",
            self,
        )
        self.worktree_checkbox.setToolTip(
            "Создать отдельное рабочее дерево и ветку agent/…, "
            "чтобы не мешать другим задачам."
        )

        self.run_button = QPushButton("Запустить", self)
        self.run_button.setObjectName("workshopAction")
        self.run_button.clicked.connect(self._start)

        self.stop_button = QPushButton("Остановить", self)
        self.stop_button.setObjectName("workshopAction")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop)

        self.new_task_button = QPushButton("Новая задача", self)
        self.new_task_button.setObjectName("workshopAction")
        self.new_task_button.setToolTip(
            "Открыть ещё одно окно агента и запустить задачу параллельно."
        )
        self.new_task_button.clicked.connect(self._open_new_task)

        self.status_label = QLabel("Готов к задаче.", self)
        self.status_label.setObjectName("dialogHint")
        self.status_label.setWordWrap(True)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.run_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.new_task_button)
        controls.addWidget(self.status_label, 1)

        self.approval_frame = QFrame(self)
        self.approval_frame.setObjectName("paramsPlate")
        self.approval_frame.setVisible(False)

        approval_layout = QVBoxLayout(self.approval_frame)
        approval_layout.setContentsMargins(10, 8, 10, 10)
        approval_layout.setSpacing(6)

        self.approval_title = QLabel(
            "ПОДТВЕРЖДЕНИЕ",
            self.approval_frame,
        )
        self.approval_title.setObjectName("paramsPlateTitle")

        self.approval_detail = QPlainTextEdit(self.approval_frame)
        self.approval_detail.setObjectName("agentTrace")
        self.approval_detail.setReadOnly(True)
        self.approval_detail.setFixedHeight(200)

        self.edit_area = QPlainTextEdit(self.approval_frame)
        self.edit_area.setObjectName("agentTask")
        self.edit_area.setFixedHeight(200)
        self.edit_area.setVisible(False)

        approval_buttons = QHBoxLayout()
        approval_buttons.setSpacing(8)

        self.approve_button = QPushButton(
            "Одобрить",
            self.approval_frame,
        )
        self.approve_button.setObjectName("workshopAction")
        self.approve_button.clicked.connect(self._approve)

        self.edit_button = QPushButton(
            "Править",
            self.approval_frame,
        )
        self.edit_button.setObjectName("workshopAction")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self._toggle_edit)

        self.reject_button = QPushButton(
            "Отклонить",
            self.approval_frame,
        )
        self.reject_button.setObjectName("workshopAction")
        self.reject_button.clicked.connect(self._reject)

        approval_buttons.addWidget(self.approve_button)
        approval_buttons.addWidget(self.edit_button)
        approval_buttons.addWidget(self.reject_button)
        approval_buttons.addStretch(1)

        approval_layout.addWidget(self.approval_title)
        approval_layout.addWidget(self.approval_detail)
        approval_layout.addWidget(self.edit_area)
        approval_layout.addLayout(approval_buttons)

        self.trace = QPlainTextEdit(self)
        self.trace.setObjectName("agentTrace")
        self.trace.setReadOnly(True)
        self.trace.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(subtitle)
        self.body_layout.addWidget(self.task_input)
        self.body_layout.addWidget(self.worktree_checkbox)
        self.body_layout.addLayout(controls)
        self.body_layout.addWidget(self.approval_frame)
        self.body_layout.addWidget(self.trace, 1)
        self.body_layout.addWidget(buttons)

    def _start(self) -> None:
        """Запускает новую задачу агента."""

        if self.job is not None and not self.job.done:
            return

        task = self.task_input.toPlainText().strip()

        if not task:
            self.status_label.setText("Сначала опиши задачу.")
            return

        model = _pick_model()

        if model is None:
            self.status_label.setText(
                "Нет доступной внешней модели: подключи её в окне «Модель»."
            )
            return

        brain = ModelBrain(
            model["model_id"],
            model.get("provider_id") or "opencode",
        )

        root = BASE_DIR
        self.worktree_path = None
        self.worktree_branch = ""

        if self.worktree_checkbox.isChecked():
            try:
                root, branch = create_worktree(BASE_DIR, task[:40])
            except WorktreeError as error:
                self.status_label.setText(f"Ветка не создана: {error}")
                return

            self.worktree_path = root
            self.worktree_branch = branch

        self.trace.clear()
        self._shown = 0
        self.approval_frame.setVisible(False)
        self._reset_edit()
        self.job = AgentJob(
            task,
            brain,
            root,
            max_steps=MAX_STEPS,
        )

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        branch_note = (
            f" · ветка {self.worktree_branch}"
            if self.worktree_branch
            else ""
        )
        self.status_label.setText(
            f"Модель: {model['name']} · шагов до {MAX_STEPS}"
            f"{branch_note}."
        )
        self._timer.start()

    def _stop(self) -> None:
        """Просит агента завершиться после текущего шага."""

        if self.job is None or self.job.done:
            return

        self.job.cancel()
        self.stop_button.setEnabled(False)
        self.status_label.setText("Останавливаю после текущего шага…")

    def _open_new_task(self) -> None:
        """Открывает ещё одно окно агента для параллельной задачи."""

        show_agent_dialog(
            self._parent,
            f"agent-{time.time_ns()}",
        )

    def _reset_edit(self) -> None:
        """Возвращает панель подтверждения к просмотру диффа."""

        self._editing = False
        self.edit_button.setText("Править")
        self.edit_button.setEnabled(False)
        self.edit_area.setVisible(False)
        self.approval_detail.setVisible(True)

    def _toggle_edit(self) -> None:
        """Переключает дифф и редактируемый текст."""

        if self.job is None or self.job.pending is None:
            return

        self._editing = not self._editing
        self.approval_detail.setVisible(not self._editing)
        self.edit_area.setVisible(self._editing)
        self.edit_button.setText(
            "К диффу" if self._editing else "Править"
        )

    def _approve(self) -> None:
        """Подтверждает действие, отправляя правку, если она есть."""

        if self.job is None:
            return

        pending = self.job.pending
        text = None

        if (
            self._editing
            and pending is not None
            and pending.new_text is not None
        ):
            text = self.edit_area.toPlainText()

        self.job.resolve_approval(True, text)
        self.approval_frame.setVisible(False)
        self._reset_edit()
        self.status_label.setText("Одобрено, продолжаю…")

    def _reject(self) -> None:
        """Отклоняет действие и возвращает агента к плану."""

        if self.job is None:
            return

        self.job.resolve_approval(False)
        self.approval_frame.setVisible(False)
        self._reset_edit()
        self.status_label.setText("Действие отклонено.")

    def _poll(self) -> None:
        """Дорисовывает новые шаги и завершает задачу."""

        job = self.job

        if job is None:
            self._timer.stop()

            return

        while self._shown < len(job.steps):
            step = job.steps[self._shown]
            self._shown += 1

            mark = STEP_MARKS.get(step.kind, "·")
            lines = [f"[{step.index}] {mark} {step.title}"]

            if step.detail:
                lines.append("    " + step.detail)

            self.trace.appendPlainText("\n".join(lines))

        pending = job.pending

        if pending is not None and not self.approval_frame.isVisible():
            self.approval_title.setText(pending.title.upper())
            self.approval_detail.setPlainText(pending.detail)
            self.edit_area.setPlainText(pending.new_text or "")
            self._reset_edit()
            self.edit_button.setEnabled(pending.new_text is not None)
            self.approval_frame.setVisible(True)
        elif pending is None and self.approval_frame.isVisible():
            self.approval_frame.setVisible(False)
            self._reset_edit()

        if not job.done:
            self.status_label.setText(
                f"Работаю… шаг {len(job.steps)} из {MAX_STEPS}."
            )

            return

        self._timer.stop()
        self.approval_frame.setVisible(False)
        self._reset_edit()
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        branch_note = (
            f" · ветка {self.worktree_branch}"
            if self.worktree_branch
            else ""
        )

        if job.cancelled:
            self.status_label.setText("Остановлено." + branch_note)
        elif job.error:
            self.status_label.setText(job.error + branch_note)

            if job.error not in self.trace.toPlainText():
                self.trace.appendPlainText("\n! " + job.error)
        else:
            self.status_label.setText(
                f"Готово за {len(job.steps)} шаг(ов)." + branch_note
            )

        if job.answer:
            self.trace.appendPlainText("\nОТВЕТ:\n" + job.answer)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Останавливает задачу, чтобы поток не жил после закрытия."""

        if self.job is not None and not self.job.done:
            self.job.cancel()

        self._timer.stop()
        super().closeEvent(event)


def show_agent_dialog(parent, key: str = "agent") -> None:
    """Открывает немодальное окно агента."""

    dialog = AgentDialog(parent)
    show_tool_window(parent, dialog, key)
