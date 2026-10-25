# Giperion/terminal/ui/agent/dialog.py                                 v001
# Окно «Агент»: задача, лента шагов, подтверждения и worktree.
# Последнее изменение: окно собрано из панелей controls/approval/trace.

import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QLabel,
)

from terminal.core.agent.tasks import (
    deserialize_steps,
)
from terminal.ui.agent.approval import ApprovalPanel
from terminal.ui.agent.constants import POLL_MS
from terminal.ui.agent.controls import AgentControls
from terminal.ui.agent.runner import AgentRunnerMixin
from terminal.ui.agent.trace import AgentTrace
from terminal.ui.agent.worktree_bar import WorktreeBar
from terminal.ui.agent_job import AgentJob
from terminal.ui.agent_tasks_dialog import show_agent_tasks_dialog
from terminal.ui.dialogs_base import SkinDialog, show_tool_window
from terminal.ui.provider_dialog import show_provider_dialog
from terminal.ui.watch_dialog import show_watch_dialog


class AgentDialog(AgentRunnerMixin, SkinDialog):
    """Окно агента; при закрытии останавливает текущую задачу."""

    def __init__(self, parent, resume: dict | None = None) -> None:
        super().__init__(
            parent,
            "Агент",
            min_width=900,
            min_height=640,
        )

        self.job: AgentJob | None = None
        self._shown = 0
        self._parent = parent
        self._resume = resume
        self.worktree_path: Path | None = None
        self.worktree_branch = ""
        self._summary_job = None

        self._build()
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

        if resume is not None:
            self._apply_resume(resume)
        else:
            self._hint_unfinished()

    def _build(self) -> None:
        """Собирает окно из панелей: поля, подтверждение и лента."""

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

        self.controls = AgentControls(self)
        self.worktree_bar = WorktreeBar(self)
        self.approval = ApprovalPanel(self)
        self.trace = AgentTrace(self)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(subtitle)
        self.body_layout.addWidget(self.controls)
        self.body_layout.addWidget(self.worktree_bar)
        self.body_layout.addWidget(self.approval)
        self.body_layout.addWidget(self.trace, 1)
        self.body_layout.addWidget(buttons)

        self.controls.run_requested.connect(self._start)
        self.controls.stop_requested.connect(self._stop)
        self.controls.new_task_requested.connect(self._open_new_task)
        self.controls.tasks_requested.connect(self._open_tasks)
        self.controls.watch_requested.connect(self._open_watch)
        self.controls.undo_requested.connect(self._undo_changes)
        self.controls.provider_requested.connect(
            lambda: show_provider_dialog(self)
        )

        self.worktree_bar.merge_requested.connect(self._merge_branch)
        self.worktree_bar.remove_requested.connect(self._remove_branch)
        self.approval.resolved.connect(self._resolve_approval)

    # --- Совместимость с прежними тестами и вызовами окна ---

    @property
    def task_input(self):
        return self.controls.task_input

    @property
    def template_combo(self):
        return self.controls.template_combo

    @property
    def worktree_checkbox(self):
        return self.controls.worktree_checkbox

    @property
    def policy_combo(self):
        return self.controls.policy_combo

    @property
    def model_combo(self):
        return self.controls.model_combo

    @property
    def steps_input(self):
        return self.controls.steps_input

    @property
    def context_input(self):
        return self.controls.context_input

    @property
    def run_button(self):
        return self.controls.run_button

    @property
    def stop_button(self):
        return self.controls.stop_button

    @property
    def provider_button(self):
        return self.controls.provider_button

    @property
    def new_task_button(self):
        return self.controls.new_task_button

    @property
    def tasks_button(self):
        return self.controls.tasks_button

    @property
    def watch_button(self):
        return self.controls.watch_button

    @property
    def undo_button(self):
        return self.controls.undo_button

    @property
    def status_label(self):
        return self.controls.status_label

    @property
    def merge_button(self):
        return self.worktree_bar.merge_button

    @property
    def remove_button(self):
        return self.worktree_bar.remove_button

    @property
    def target_combo(self):
        return self.worktree_bar.target_combo

    @property
    def approval_frame(self):
        return self.approval

    @property
    def allow_checkbox(self):
        return self.approval.allow_checkbox

    @property
    def edit_button(self):
        return self.approval.edit_button

    @property
    def approval_title(self):
        return self.approval.title

    @property
    def approval_detail(self):
        return self.approval.detail

    @property
    def old_view(self):
        return self.approval.old_view

    @property
    def edit_area(self):
        return self.approval.edit_area

    def _open_tasks(self) -> None:
        """Открывает список сохранённых задач."""

        show_agent_tasks_dialog(
            self._parent,
            on_resume=self._resume_task,
        )

    def _open_watch(self) -> None:
        """Открывает наблюдатель за файлами."""

        show_watch_dialog(self._parent)

    def _hint_unfinished(self) -> None:
        """Подсказывает про незавершённую задачу при открытии окна."""

        from terminal.core.agent.tasks import (
            STATUS_RUNNING,
            list_states,
        )

        running = [
            state
            for state in list_states(limit=20)
            if state.get("status") == STATUS_RUNNING
        ]

        if not running:
            return

        task = str(running[0].get("task") or "").splitlines()

        self.status_label.setText(
            "Есть незавершённая задача"
            + (f": «{task[0][:60]}»" if task else "")
            + ". Открой «Задачи…», чтобы продолжить."
        )

    def _apply_resume(self, state: dict) -> None:
        """Заполняет окно сохранённой задачей."""

        self.task_input.setPlainText(str(state.get("task") or ""))

        policy = str(state.get("policy") or "")
        index = self.policy_combo.findData(policy)

        if index >= 0:
            self.policy_combo.setCurrentIndex(index)

        branch = str(state.get("worktree_branch") or "")
        root = Path(str(state.get("root") or ""))

        if branch and ".agent_worktrees" in root.parts:
            self.worktree_path = root
            self.worktree_branch = branch
            self.worktree_checkbox.setChecked(True)
            self.worktree_checkbox.setEnabled(False)

        steps = deserialize_steps(state.get("steps"))

        for step in steps:
            self.trace.append_step(step)

        self._shown = len(steps)
        self.status_label.setText(
            "Продолжение задачи. Проверь текст и нажми «Запустить»."
        )



    def _open_new_task(self) -> None:
        """Открывает ещё одно окно агента для параллельной задачи."""

        show_agent_dialog(
            self._parent,
            f"agent-{time.time_ns()}",
        )

    def _resume_task(self, state: dict) -> None:
        """Открывает выбранную задачу с сохранённой историей."""

        task_id = str(state.get("id") or "")

        show_agent_dialog(
            self._parent,
            f"agent-resume-{task_id}",
            resume=state,
        )



    def _approve(self) -> None:
        """Подтверждает действие, отправляя правку, если она есть."""

        self.approval.approve()

    def _reject(self) -> None:
        """Отклоняет действие и возвращает агента к плану."""

        self.approval.reject()

    def _resolve_approval(
        self,
        approved: bool,
        text,
        remember: bool,
    ) -> None:
        """Передаёт решение панели в задачу и обновляет статус."""

        if self.job is None:
            return

        self.job.resolve_approval(approved, text, remember)
        self.approval.hide_panel()

        if not approved:
            self.status_label.setText("Действие отклонено.")

            return

        self.status_label.setText(
            "Одобрено до конца задачи, продолжаю…"
            if remember
            else "Одобрено, продолжаю…"
        )



    def closeEvent(self, event: QCloseEvent) -> None:
        """Останавливает задачу, чтобы поток не жил после закрытия."""

        if self.job is not None and not self.job.done:
            self.job.cancel()

        self._timer.stop()
        super().closeEvent(event)


def show_agent_dialog(
    parent,
    key: str = "agent",
    resume: dict | None = None,
) -> None:
    """Открывает немодальное окно агента."""

    dialog = AgentDialog(parent, resume)
    show_tool_window(parent, dialog, key)
