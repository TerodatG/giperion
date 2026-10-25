# Giperion/terminal/ui/agent_job.py                                  v001
# Фоновый запуск read-only агента и накопление шагов для окна.
# Последнее изменение: первый вариант — без записи и команд.

import threading
import time
from pathlib import Path

from terminal.core.agent.loop import run_agent
from terminal.core.agent.protocol import (
    AgentStep,
    ApprovalRequest,
    ApprovalResult,
)
from terminal.core.agent.runs import record_run


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
    ) -> None:
        self.steps: list[AgentStep] = []
        self.answer = ""
        self.error = ""
        self.cancelled = False
        self.done = False
        self.pending: ApprovalRequest | None = None
        self.approvals = 0
        self.duration_s = 0.0

        self._task = task
        self._brain = brain
        self._root = root
        self._max_steps = max_steps
        self._model_name = model_name
        self._stop = threading.Event()
        self._approval = threading.Event()
        self._approved = False
        self._approval_text: str | None = None
        self._started = time.monotonic()

        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self._thread.start()

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
        self._approval.clear()

        while not self._approval.wait(0.2):
            if self._stop.is_set():
                self.pending = None

                return ApprovalResult(False)

        self.pending = None

        return ApprovalResult(self._approved, self._approval_text)

    def resolve_approval(
        self,
        approved: bool,
        text: str | None = None,
    ) -> None:
        """Передаёт решение кнопки и, если нужно, правку текста."""

        self._approved = bool(approved)
        self._approval_text = text
        self._approval.set()

    def _on_step(self, step: AgentStep) -> None:
        """Складывает шаг в общий список для окна."""

        self.steps.append(step)

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
            )

            self.answer = result.answer
            self.error = result.error
            self.cancelled = result.cancelled

            if not self.steps and result.steps:
                self.steps = list(result.steps)
        except Exception as error:  # noqa: BLE001 — покажем в окне
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.duration_s = time.monotonic() - self._started
            record_run(
                self._task,
                self._model_name,
                len(self.steps),
                self.approvals,
                self.duration_s,
                self.answer,
                self.error,
                self.cancelled,
            )
            self.done = True
