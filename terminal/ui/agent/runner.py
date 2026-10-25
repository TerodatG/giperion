# Giperion/terminal/ui/agent/runner.py                                 v001
# Исполнение задачи: запуск, опрос, остановка, ветка и откат.
# Последнее изменение: вынесено из dialog отдельным миксином.

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from config import BASE_DIR
from terminal.core.agent.brain import ModelBrain
from terminal.core.agent.providers import (
    NativeBrain,
    provider_from_settings,
)
from terminal.core.agent.rollback import rollback_run
from terminal.core.agent.settings import (
    budget_limits,
    set_approval_policy,
    set_context_limit_chars,
    set_max_steps,
    set_model_choice,
)
from terminal.core.agent.summary import format_changes
from terminal.core.agent.tasks import (
    deserialize_history,
    deserialize_steps,
)
from terminal.core.agent.worktrees import (
    WorktreeError,
    create_worktree,
    merge_worktree,
    remove_worktree,
)
from terminal.ui.agent_job import AgentJob


class AgentRunnerMixin:
    """Запуск и ведение задачи; окно даёт панели и таймер."""

    def _start(self) -> None:
        """Запускает новую задачу агента."""

        if self.job is not None and not self.job.done:
            return

        task = self.task_input.toPlainText().strip()

        if not task:
            self.status_label.setText("Сначала опиши задачу.")
            return

        self.undo_button.setVisible(False)
        self._summary_job = None

        limits = budget_limits()
        context_chars = int(self.context_input.value())
        steps_limit = int(self.steps_input.value())

        set_max_steps(steps_limit)
        set_context_limit_chars(context_chars)

        choice = self.model_combo.currentData()

        if not isinstance(choice, dict):
            self.status_label.setText(
                "Нет доступной модели: включи провайдера в «Провайдер…» "
                "или добавь модель в каталог."
            )
            return

        if choice.get("kind") == "native":
            native = provider_from_settings()

            if native is None:
                self.status_label.setText(
                    "Провайдер не настроен: заполни адрес, модель и ключ "
                    "в окне «Провайдер…»."
                )
                return

            brain = NativeBrain(native, limits)
            model_name = f"native · {native.model}"
            set_model_choice("native")
        else:
            model = choice.get("model") or {}
            model_id = str(model.get("model_id") or "")

            if not model_id:
                self.status_label.setText(
                    "У выбранной модели нет идентификатора."
                )
                return

            brain = ModelBrain(
                model_id,
                model.get("provider_id") or "opencode",
            )
            model_name = str(model.get("name") or model_id)
            set_model_choice(str(model.get("id") or model_id))

        if self._resume_current(
            task,
            brain,
            model_name,
            steps_limit,
            context_chars,
            limits,
        ):
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
        self.approval.hide_panel()

        policy = self.policy_combo.currentData() or "confirm"
        set_approval_policy(policy)
        self.job = AgentJob(
            task,
            brain,
            root,
            max_steps=steps_limit,
            model_name=model_name,
            policy=policy,
            worktree_branch=self.worktree_branch,
            budget=limits,
            max_prompt_chars=context_chars,
        )

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.worktree_bar.show_actions(False)

        branch_note = (
            f" · ветка {self.worktree_branch}"
            if self.worktree_branch
            else ""
        )
        self.status_label.setText(
            f"Модель: {model_name} · шагов до {steps_limit}"
            f"{branch_note}."
        )
        self._timer.start()

    def _resume_current(
        self,
        task: str,
        brain,
        model_name: str,
        steps_limit: int,
        context_chars: int,
        limits,
    ) -> bool:
        """Продолжает сохранённую задачу, если её текст совпал."""

        resume = self._resume

        if not resume or task != str(resume.get("task") or ""):
            return False

        self._resume = None
        resume_root = Path(str(resume.get("root") or ""))

        if not resume_root.exists():
            self.status_label.setText(
                f"Папка задачи не найдена: {resume_root}"
            )

            return True

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
            max_steps=steps_limit,
            model_name=model_name,
            policy=policy,
            task_id=str(resume.get("id") or "") or None,
            initial_history=history,
            initial_steps=steps,
            worktree_branch=branch,
            budget=limits,
            max_prompt_chars=context_chars,
        )

        self._shown = len(steps)
        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("Продолжаю сохранённую задачу…")
        self._timer.start()

        return True

    def _stop(self) -> None:
        """Просит агента завершиться после текущего шага."""

        if self.job is None or self.job.done:
            return

        self.job.cancel()
        self.stop_button.setEnabled(False)
        self.status_label.setText("Останавливаю после текущего шага…")

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
        self.worktree_bar.show_actions(False)

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
        self.worktree_bar.show_actions(False)
        self.status_label.setText(message)

    def _poll(self) -> None:
        """Дорисовывает новые шаги и завершает задачу."""

        job = self.job

        if job is None:
            self._timer.stop()

            return

        self._append_steps(job)
        self._sync_approval(job)

        if not job.done:
            self._show_progress(job)

            return

        self._finish_job(job)

    def _append_steps(self, job) -> None:
        """Добавляет новые шаги в ленту."""

        while self._shown < len(job.steps):
            step = job.steps[self._shown]
            self._shown += 1
            self.trace.append_step(step)

    def _sync_approval(self, job) -> None:
        """Показывает или скрывает панель подтверждения."""

        pending = job.pending

        if pending is not None and not self.approval.isVisible():
            self.approval.show_request(pending)
        elif pending is None and self.approval.isVisible():
            self.approval.hide_panel()

    def _show_progress(self, job) -> None:
        """Статус во время работы."""

        spend = job.live_tokens
        tail = job.partial.replace("\n", " ").strip()

        self.status_label.setText(
            f"Работаю… шаг {len(job.steps)} из "
            f"{getattr(job, 'max_steps', 0)}"
            + (f" · {spend // 1000}k токенов" if spend else "")
            + (f" · «{tail[-70:]}»" if tail else "")
            + "."
        )

    def _finish_job(self, job) -> None:
        """Показывает итог и готовит откат изменений."""

        self._timer.stop()
        self.approval.hide_panel()
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        show_worktree_actions = bool(self.worktree_path)
        self.worktree_bar.show_actions(show_worktree_actions)

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
            self._show_success(job, branch_note)

        if job.answer:
            self.trace.appendPlainText("\nОТВЕТ:\n" + job.answer)

        changes = list(getattr(job, "changes", []) or [])
        has_changes = bool(getattr(job, "changed", set()))

        self.undo_button.setVisible(has_changes)
        self.undo_button.setEnabled(bool(changes))

        if changes and self._summary_job is not job:
            self._summary_job = job
            self.trace.appendPlainText(
                "\nИЗМЕНЕНИЯ:\n" + format_changes(changes)
            )

    def _show_success(self, job, branch_note: str) -> None:
        """Статус успешного завершения."""

        allowed = (
            f" · разрешено до конца: {len(job.allowed)}"
            if job.allowed
            else ""
        )
        spend = (
            f" · {job.tokens // 1000}k токенов"
            + (" · " if job.cost > 0 else "")
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

    def _undo_changes(self) -> None:
        """Возвращает файлы задачи к состоянию до запуска."""

        job = self.job

        if job is None or not getattr(job, "changed", set()):
            return

        record = job.rollback_record()
        ready = [
            item["path"]
            for item in (getattr(job, "changes", []) or [])
            if item.get("available")
        ]

        if not ready:
            self.status_label.setText(
                "Откат невозможен: резервные копии не найдены."
            )

            return

        answer = QMessageBox.question(
            self,
            "Откатить изменения",
            "Вернуть к состоянию до задачи:\n\n"
            + "\n".join(ready[:10])
            + (
                f"\n… и ещё {len(ready) - 10}"
                if len(ready) > 10
                else ""
            )
            + "\n\nТекущие изменения этих файлов будут потеряны.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        lines = rollback_run(Path(record["root"]), record)

        self.trace.appendPlainText("\nОТКАТ:\n" + "\n".join(lines))
        self.status_label.setText(
            "Файлы возвращены к состоянию до задачи."
        )
        self.undo_button.setEnabled(False)
