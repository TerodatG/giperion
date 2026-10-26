# Giperion/terminal/ui/agent_job.py                                  v001
# Фоновый запуск read-only агента и накопление шагов для окна.
# Последнее изменение: первый вариант — без записи и команд.

import threading
import time
from pathlib import Path

from terminal.core.agent import tasks as task_store
from terminal.core.agent.loop import run_agent
from terminal.core.agent.protocol import (
    AgentStep,
    ApprovalRequest,
    ApprovalResult,
)
from terminal.core.agent.runs import record_run
from terminal.core.agent.summary import changes_of


def _step_timeout_setting() -> int:
    """Таймаут шага из настроек; при ошибке — 180 секунд."""

    try:
        from terminal.core.agent.settings import step_timeout

        return int(step_timeout())
    except Exception:  # noqa: BLE001 — настройки не обязательны
        return 180


class AgentJob:
    """Выполняет задачу агента в отдельном потоке.

    Окно опрашивает job и дорисовывает шаги, поэтому интерфейс не
    замирает на время запросов к модели.
    """

    def __init__(
        self,
        task: str,
        brain,
        root: Path,
        max_steps: int = 8,
        model_name: str = "",
        policy: str = "confirm",
        task_id: str | None = None,
        initial_history=None,
        initial_steps=None,
        worktree_branch: str = "",
        persist: bool = True,
        budget=None,
        max_prompt_chars: int = 60_000,
        step_timeout: float | None = None,
    ) -> None:
        self.steps: list[AgentStep] = list(initial_steps or [])
        self.answer = ""
        self.error = ""
        self.cancelled = False
        self.done = False
        self.pending: ApprovalRequest | None = None
        self.approvals = 0
        self.duration_s = 0.0
        self.context_chars = 0
        self.tokens = 0
        self.cost = 0.0
        self.partial = ""
        # Файлы, которые агент изменил: нужны для отката прогона.
        self.changed: set[str] = set()
        self.changes: list[dict] = []
        self._started_at = self._now()
        self._finished_at = ""
        self._budget = budget
        self._max_prompt_chars = max(8_000, int(max_prompt_chars))
        self._step_timeout = (
            float(step_timeout)
            if step_timeout is not None
            else float(_step_timeout_setting())
        )

        self._task = task
        self._brain = brain
        self._root = root
        self._max_steps = max_steps
        self.max_steps = max(1, int(max_steps))
        self._model_name = model_name
        self._policy = policy
        self._initial_history = list(initial_history or [])
        # Разрешения «до конца задачи»: только для этого прогона.
        self.allowed: set[str] = set()
        self._remember = False
        self._stop = threading.Event()
        self._approval = threading.Event()
        self._approved = False
        self._approval_text: str | None = None
        self._started = time.monotonic()

        # Поток ответа: мозг с tool calls умеет отдавать куски текста.
        if hasattr(self._brain, "on_delta"):
            self._brain.on_delta = self._on_delta

        self.task_id = task_id or task_store.new_task_id()
        self._persist = persist
        self._state = {
            "id": self.task_id,
            "task": task,
            "model": model_name,
            "policy": policy,
            "root": str(root),
            "worktree_branch": worktree_branch,
            "status": task_store.STATUS_RUNNING,
            "answer": "",
            "error": "",
            "steps": task_store.serialize_steps(self.steps),
            "history": task_store.serialize_history(
                self._initial_history
            ),
            "files": [],
            "created_at": self._now(),
        }

        if self._persist:
            task_store.save_state(self._state)

        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self._thread.start()

    @staticmethod
    def _now() -> str:
        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    @property
    def live_tokens(self) -> int:
        """Токены, потраченные к этому моменту."""

        return int(getattr(self._brain, "total_tokens", 0) or 0)

    @property
    def live_cost(self) -> float:
        """Стоимость, потраченная к этому моменту."""

        return float(getattr(self._brain, "cost", 0.0) or 0.0)

    @property
    def retries(self) -> int:
        """Сколько раз провайдер повторял временно неудачные запросы."""

        provider = getattr(self._brain, "provider", None)

        return int(getattr(provider, "retry_count", 0) or 0)

    def rollback_record(self) -> dict:
        """Запись для summary.rollback: файлы и окно времени прогона."""

        return {
            "root": str(self._root),
            "files": sorted(self.changed),
            "started_at": self._started_at,
            "created_at": self._finished_at or self._now(),
        }

    def cancel(self) -> None:
        """Просит цикл остановиться после текущего шага."""

        self._stop.set()
        self._approval.set()

    def request_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalResult:
        """Ждёт решения пользователя, не блокируя интерфейс."""

        self.pending = request
        self.approvals += 1
        self._approved = False
        self._approval_text = None
        self._remember = False
        self._approval.clear()

        while not self._approval.wait(0.2):
            if self._stop.is_set():
                self.pending = None

                return ApprovalResult(False)

        self.pending = None

        return ApprovalResult(
            self._approved,
            self._approval_text,
            self._remember,
        )

    def resolve_approval(
        self,
        approved: bool,
        text: str | None = None,
        remember: bool = False,
    ) -> None:
        """Передаёт решение кнопки, правку текста и «не спрашивать»."""

        self._approved = bool(approved)
        self._approval_text = text
        self._remember = bool(remember)
        self._approval.set()

    def _on_step(self, step: AgentStep) -> None:
        """Складывает шаг в общий список для окна."""

        self.partial = ""
        self.steps.append(step)

        if self._persist:
            self._state["steps"] = task_store.serialize_steps(
                self.steps
            )
            task_store.save_state(self._state)

    def _on_history(self, history) -> None:
        """Сохраняет историю для продолжения задачи."""

        for call, _result in history:
            if call.tool not in ("apply_patch", "write_file"):
                continue

            path = str(call.args.get("path") or "").strip()

            if path:
                self.changed.add(path)

        if self._persist:
            self._state["history"] = task_store.serialize_history(
                history
            )
            self._state["files"] = sorted(self.changed)
            task_store.save_state(self._state)

    def _on_delta(self, piece: str) -> None:
        """Копит кусок потокового ответа, чтобы окно показало хвост."""

        self.partial = (self.partial + piece)[-200:]

    def _run(self) -> None:
        """Запускает цикл агента и запоминает итог."""

        try:
            result = run_agent(
                self._task,
                self._brain,
                self._root,
                max_steps=self._max_steps,
                on_step=self._on_step,
                should_stop=self._stop.is_set,
                approve=self.request_approval,
                policy=self._policy,
                initial_history=self._initial_history,
                on_history=self._on_history,
                allowed=self.allowed,
                budget=self._budget,
                max_prompt_chars=self._max_prompt_chars,
                step_timeout=self._step_timeout,
            )

            self.answer = result.answer
            self.error = result.error
            self.cancelled = result.cancelled
            self.context_chars = result.context_chars

            if not self.steps and result.steps:
                self.steps = list(result.steps)
        except Exception as error:  # noqa: BLE001 — покажем в окне
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.duration_s = time.monotonic() - self._started
            self.tokens = int(getattr(self._brain, "total_tokens", 0) or 0)
            self.cost = float(getattr(self._brain, "cost", 0.0) or 0.0)
            self._finished_at = self._now()

            if self.changed:
                try:
                    self.changes = changes_of(
                        self._root,
                        self.rollback_record(),
                    )
                except Exception:  # noqa: BLE001 — сводка не должна ломать
                    self.changes = []

            record_run(
                self._task,
                self._model_name,
                len(self.steps),
                self.approvals,
                self.duration_s,
                self.answer,
                self.error,
                self.cancelled,
                self.tokens,
                self.cost,
                self.retries,
                sorted(self.changed),
                self._started_at,
                str(self._root),
            )

            if self._persist:
                if self.cancelled:
                    status = task_store.STATUS_CANCELLED
                elif self.error:
                    status = task_store.STATUS_ERROR
                else:
                    status = task_store.STATUS_DONE

                self._state.update(
                    {
                        "status": status,
                        "answer": self.answer,
                        "error": self.error,
                        "files": sorted(self.changed),
                        "steps": task_store.serialize_steps(
                            self.steps
                        ),
                    }
                )
                task_store.save_state(self._state)

            self.done = True
