# Giperion/terminal/ui/agent_dialog.py                               v002
# Окно «Агент»: задача, лента шагов, подтверждения и worktree.
# Последнее изменение: отдельная ветка и параллельные задачи.

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QCloseEvent,
    QColor,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import BASE_DIR
from terminal.core.agent.brain import ModelBrain
from terminal.core.agent.diff_marks import (
    LineSpan,
    diff_marks as build_marks,
)
from terminal.core.agent.providers import NativeBrain
from terminal.core.agent.settings import (
    approval_policy,
    budget_limits,
    provider_from_settings,
    set_approval_policy,
)
from terminal.core.agent.tasks import (
    deserialize_history,
    deserialize_steps,
)
from terminal.core.agent.worktrees import (
    WorktreeError,
    create_worktree,
    current_branch,
    list_branches,
    merge_worktree,
    remove_worktree,
)
from terminal.core.helper_model import get_helper_model
from terminal.core.model_registry import (
    DEFAULT_MODEL_ID,
    get_active_model,
)
from terminal.ui.agent_job import AgentJob
from terminal.ui.dialogs_base import SkinDialog, show_tool_window
from terminal.ui.agent_tasks_dialog import show_agent_tasks_dialog
from terminal.ui.provider_dialog import show_provider_dialog

MAX_STEPS = 12
POLL_MS = 120

STEP_MARKS = {
    "tool": "→",
    "answer": "✓",
    "error": "!",
    "approval": "▣",
    "subagent": "↳",
    "secret": "▤",
    "budget": "Σ",
}

REMEMBER_TITLES = {
    "apply_patch": "Больше не спрашивать этот файл",
    "write_file": "Больше не спрашивать этот файл",
    "run_tests": "Больше не спрашивать про тесты",
    "run_command": "Больше не спрашивать эту команду",
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

    def __init__(self, parent, resume: dict | None = None) -> None:
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
        self._resume = resume
        self.worktree_path: Path | None = None
        self.worktree_branch = ""

        self._build()
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

        self._highlight_timer = QTimer(self)
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.setInterval(180)
        self._highlight_timer.timeout.connect(
            self._refresh_highlights
        )

        if resume is not None:
            self._apply_resume(resume)

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

        self.provider_button = QPushButton("Провайдер…", self)
        self.provider_button.setObjectName("workshopAction")
        self.provider_button.setToolTip(
            "Адрес, ключ и модель провайдера с настоящими tool calls."
        )
        self.provider_button.clicked.connect(
            lambda: show_provider_dialog(self)
        )

        self.policy_combo = QComboBox(self)
        self.policy_combo.setObjectName("approvalPolicy")
        self.policy_combo.addItem("Спрашивать всё", "confirm")
        self.policy_combo.addItem("Доверять правкам", "trust")
        self.policy_combo.addItem("Только чтение", "read")
        self.policy_combo.setToolTip(
            "Только чтение — запись запрещена; "
            "Доверять правкам — apply_patch и запись без вопросов, "
            "но команды и коммиты всё равно спрашивают."
        )

        current_policy = approval_policy()
        policy_index = self.policy_combo.findData(current_policy)

        if policy_index >= 0:
            self.policy_combo.setCurrentIndex(policy_index)

        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        model_row.addWidget(self.worktree_checkbox)
        model_row.addWidget(self.provider_button)
        model_row.addWidget(self.policy_combo)
        model_row.addStretch(1)

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

        self.tasks_button = QPushButton("Задачи…", self)
        self.tasks_button.setObjectName("workshopAction")
        self.tasks_button.setToolTip(
            "Сохранённые задачи: продолжить или удалить."
        )
        self.tasks_button.clicked.connect(
            lambda: show_agent_tasks_dialog(self._parent)
        )

        self.status_label = QLabel("Готов к задаче.", self)
        self.status_label.setObjectName("dialogHint")
        self.status_label.setWordWrap(True)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.run_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.new_task_button)
        controls.addWidget(self.tasks_button)
        controls.addWidget(self.status_label, 1)

        self.merge_button = QPushButton("Слить ветку", self)
        self.merge_button.setObjectName("workshopAction")
        self.merge_button.setVisible(False)
        self.merge_button.clicked.connect(self._merge_branch)

        self.remove_button = QPushButton("Удалить ветку", self)
        self.remove_button.setObjectName("workshopAction")
        self.remove_button.setVisible(False)
        self.remove_button.clicked.connect(self._remove_branch)

        self.target_combo = QComboBox(self)
        self.target_combo.setObjectName("targetBranch")
        self.target_combo.setVisible(False)
        self.target_combo.setToolTip(
            "В какую ветку слить результат задачи."
        )

        worktree_row = QHBoxLayout()
        worktree_row.setSpacing(8)
        worktree_row.addWidget(self.merge_button)
        worktree_row.addWidget(self.target_combo)
        worktree_row.addWidget(self.remove_button)
        worktree_row.addStretch(1)

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

        self.edit_split = QWidget(self.approval_frame)
        self.edit_split.setVisible(False)

        split_layout = QHBoxLayout(self.edit_split)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(6)

        old_column = QVBoxLayout()
        old_column.setSpacing(2)
        old_caption = QLabel("БЫЛО", self.edit_split)
        old_caption.setObjectName("paramsPlateTitle")
        self.old_view = QPlainTextEdit(self.edit_split)
        self.old_view.setObjectName("agentTrace")
        self.old_view.setReadOnly(True)
        self.old_view.setFixedHeight(200)
        old_column.addWidget(old_caption)
        old_column.addWidget(self.old_view)

        new_column = QVBoxLayout()
        new_column.setSpacing(2)
        new_caption = QLabel("СТАНЕТ", self.edit_split)
        new_caption.setObjectName("paramsPlateTitle")
        self.edit_area = QPlainTextEdit(self.edit_split)
        self.edit_area.setObjectName("agentTask")
        self.edit_area.setFixedHeight(200)
        self.edit_area.textChanged.connect(
            self._schedule_highlights
        )
        new_column.addWidget(new_caption)
        new_column.addWidget(self.edit_area)

        split_layout.addLayout(old_column, 1)
        split_layout.addLayout(new_column, 1)

        approval_buttons = QHBoxLayout()
        approval_buttons.setSpacing(8)

        self.allow_checkbox = QCheckBox(
            "Не спрашивать это до конца задачи",
            self.approval_frame,
        )
        self.allow_checkbox.setObjectName("approvalPolicy")
        self.allow_checkbox.setVisible(False)

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
        approval_layout.addWidget(self.edit_split)
        approval_layout.addWidget(self.allow_checkbox)
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
        self.body_layout.addLayout(model_row)
        self.body_layout.addLayout(controls)
        self.body_layout.addLayout(worktree_row)
        self.body_layout.addWidget(self.approval_frame)
        self.body_layout.addWidget(self.trace, 1)
        self.body_layout.addWidget(buttons)

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
            self._append_step(step)

        self._shown = len(steps)
        self.status_label.setText(
            "Продолжение задачи. Проверь текст и нажми «Запустить»."
        )

    def _append_step(self, step) -> None:
        """Добавляет один шаг в ленту."""

        mark = STEP_MARKS.get(step.kind, "·")
        lines = [f"[{step.index}] {mark} {step.title}"]

        if step.detail:
            lines.append("    " + step.detail)

        self.trace.appendPlainText("\n".join(lines))

    def _start(self) -> None:
        """Запускает новую задачу агента."""

        if self.job is not None and not self.job.done:
            return

        task = self.task_input.toPlainText().strip()

        if not task:
            self.status_label.setText("Сначала опиши задачу.")
            return

        native = provider_from_settings()
        limits = budget_limits()

        if native is not None:
            brain = NativeBrain(native, limits)
            model_name = f"native · {native.model}"
        else:
            model = _pick_model()

            if model is None:
                self.status_label.setText(
                    "Нет доступной внешней модели: подключи её в окне "
                    "«Модель» или задай AGENT_BASE_URL/AGENT_API_KEY/"
                    "AGENT_MODEL."
                )
                return

            brain = ModelBrain(
                model["model_id"],
                model.get("provider_id") or "opencode",
            )
            model_name = model["name"]

        resume = self._resume

        if resume and task == str(resume.get("task") or ""):
            self._resume = None
            resume_root = Path(str(resume.get("root") or ""))

            if not resume_root.exists():
                self.status_label.setText(
                    f"Папка задачи не найдена: {resume_root}"
                )
                return

            history = deserialize_history(resume.get("history"))
            steps = deserialize_steps(resume.get("steps"))
            branch = str(resume.get("worktree_branch") or "")

            self.worktree_branch = branch
            self.worktree_path = (
                resume_root
                if ".agent_worktrees" in resume_root.parts
                else None
            )

            policy = self.policy_combo.currentData() or "confirm"
            set_approval_policy(policy)

            self.job = AgentJob(
                task,
                brain,
                resume_root,
                max_steps=MAX_STEPS,
                model_name=model_name,
                policy=policy,
                task_id=str(resume.get("id") or "") or None,
                initial_history=history,
                initial_steps=steps,
                worktree_branch=branch,
                budget=limits,
            )

            self._shown = len(steps)
            self.run_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_label.setText(
                "Продолжаю сохранённую задачу…"
            )
            self._timer.start()

            return

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

        policy = self.policy_combo.currentData() or "confirm"
        set_approval_policy(policy)
        self.job = AgentJob(
            task,
            brain,
            root,
            max_steps=MAX_STEPS,
            model_name=model_name,
            policy=policy,
            worktree_branch=self.worktree_branch,
            budget=limits,
        )

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.merge_button.setVisible(False)
        self.remove_button.setVisible(False)
        self.target_combo.setVisible(False)

        branch_note = (
            f" · ветка {self.worktree_branch}"
            if self.worktree_branch
            else ""
        )
        self.status_label.setText(
            f"Модель: {model_name} · шагов до {MAX_STEPS}"
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

    def _merge_branch(self) -> None:
        """Сливает ветку задачи в текущую ветку проекта."""

        if not self.worktree_path or not self.worktree_branch:
            return

        target = self.target_combo.currentText().strip()

        try:
            message = merge_worktree(
                BASE_DIR,
                self.worktree_branch,
                target,
            )
        except WorktreeError as error:
            self.status_label.setText(f"Слияние не удалось: {error}")

            return

        where = f" в {target}" if target else ""
        self.status_label.setText(
            f"Слито{where}: " + message.splitlines()[0][:200]
        )
        self.merge_button.setVisible(False)
        self.remove_button.setVisible(False)
        self.target_combo.setVisible(False)

    def _remove_branch(self) -> None:
        """Удаляет дерево и ветку задачи после подтверждения."""

        if not self.worktree_path or not self.worktree_branch:
            return

        answer = QMessageBox.question(
            self,
            "Удалить ветку?",
            "Дерево "
            f"{self.worktree_path.name} и ветка "
            f"{self.worktree_branch} будут удалены. "
            "Незакоммиченные изменения в дереве пропадут.",
        )

        if answer != QMessageBox.Yes:
            return

        try:
            message = remove_worktree(
                BASE_DIR,
                self.worktree_path,
                self.worktree_branch,
            )
        except WorktreeError as error:
            self.status_label.setText(f"Не удалено: {error}")

            return

        self.worktree_path = None
        self.worktree_branch = ""
        self.merge_button.setVisible(False)
        self.remove_button.setVisible(False)
        self.target_combo.setVisible(False)
        self.status_label.setText(message)

    def _schedule_highlights(self) -> None:
        """Пересчитывает подсветку после правки текста."""

        self._highlight_timer.start()

    def _selections(
        self,
        view: QPlainTextEdit,
        lines: frozenset[int],
        spans: tuple[LineSpan, ...],
        color: str,
    ) -> list:
        """Собирает подсветку строк и слов одного редактора."""

        selections = []
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(color))

        for index in sorted(lines):
            block = view.document().findBlockByNumber(index)

            if not block.isValid():
                continue

            cursor = QTextCursor(block)
            cursor.select(QTextCursor.LineUnderCursor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = fmt

            selections.append(selection)

        for span in spans:
            block = view.document().findBlockByNumber(span.line)

            if not block.isValid():
                continue

            cursor = QTextCursor(block)
            start = block.position() + span.start
            end = block.position() + span.end

            if end <= start:
                continue

            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = fmt

            selections.append(selection)

        return selections

    def _refresh_highlights(self) -> None:
        """Подсвечивает изменённые строки и слова с обеих сторон."""

        if self.job is None or self.job.pending is None:
            return

        marks = build_marks(
            self.old_view.toPlainText(),
            self.edit_area.toPlainText(),
        )

        self.old_view.setExtraSelections(
            self._selections(
                self.old_view,
                marks.old_lines,
                marks.old_spans,
                "#4a1f1a",
            )
        )
        self.edit_area.setExtraSelections(
            self._selections(
                self.edit_area,
                marks.new_lines,
                marks.new_spans,
                "#123d1f",
            )
        )

    def _reset_edit(self) -> None:
        """Возвращает панель подтверждения к просмотру диффа."""

        self._editing = False
        self.edit_button.setText("Править")
        self.edit_button.setEnabled(False)
        self.edit_split.setVisible(False)
        self.approval_detail.setVisible(True)
        self.old_view.setExtraSelections([])
        self.edit_area.setExtraSelections([])

    def _toggle_edit(self) -> None:
        """Переключает дифф и редактируемый текст."""

        if self.job is None or self.job.pending is None:
            return

        self._editing = not self._editing
        self.approval_detail.setVisible(not self._editing)
        self.edit_split.setVisible(self._editing)
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

        remember = bool(
            pending is not None
            and pending.key
            and self.allow_checkbox.isChecked()
        )

        self.job.resolve_approval(True, text, remember)
        self.approval_frame.setVisible(False)
        self._reset_edit()
        self.status_label.setText(
            "Одобрено до конца задачи, продолжаю…"
            if remember
            else "Одобрено, продолжаю…"
        )

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
            self._append_step(step)

        pending = job.pending

        if pending is not None and not self.approval_frame.isVisible():
            self.approval_title.setText(pending.title.upper())
            self.approval_detail.setPlainText(pending.detail)
            self.old_view.setPlainText(pending.old_text or "")
            self.edit_area.setPlainText(pending.new_text or "")
            self._reset_edit()
            self.edit_button.setEnabled(pending.new_text is not None)

            remember_title = REMEMBER_TITLES.get(pending.kind, "")

            self.allow_checkbox.setText(remember_title)
            self.allow_checkbox.setChecked(False)
            self.allow_checkbox.setVisible(
                bool(remember_title and pending.key)
            )

            self._refresh_highlights()
            self.approval_frame.setVisible(True)
        elif pending is None and self.approval_frame.isVisible():
            self.approval_frame.setVisible(False)
            self._reset_edit()

        if not job.done:
            spend = job.live_tokens

            self.status_label.setText(
                f"Работаю… шаг {len(job.steps)} из {MAX_STEPS}"
                + (f" · {spend // 1000}k токенов" if spend else "")
                + "."
            )

            return

        self._timer.stop()
        self.approval_frame.setVisible(False)
        self._reset_edit()
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        show_worktree_actions = bool(self.worktree_path)
        self.merge_button.setVisible(show_worktree_actions)
        self.remove_button.setVisible(show_worktree_actions)
        self.target_combo.setVisible(show_worktree_actions)

        if show_worktree_actions:
            branches = list_branches(BASE_DIR)
            self.target_combo.clear()
            self.target_combo.addItems(branches)

            current = current_branch(BASE_DIR)

            if current:
                self.target_combo.setCurrentText(current)

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
            allowed = (
                f" · разрешено до конца: {len(job.allowed)}"
                if job.allowed
                else ""
            )

            spend = (
                f" · {job.tokens // 1000}k токенов"
                + (f" · ${job.cost:.4f}" if job.cost > 0 else "")
                if job.tokens
                else ""
            )

            self.status_label.setText(
                f"Готово за {len(job.steps)} шаг(ов)"
                f" · {job.duration_s:.1f} с"
                f" · подтверждений: {job.approvals}"
                f" · контекст {job.context_chars // 1000}k"
                + spend
                + allowed
                + branch_note
            )

        if job.answer:
            self.trace.appendPlainText("\nОТВЕТ:\n" + job.answer)

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
