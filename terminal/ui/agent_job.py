# Giperion/terminal/ui/agent_job.py                                  v001
# Фоновый запуск read-only агента и накопление шагов для окна.
# Последнее изменение: первый вариант — без записи и команд.

import threading
from pathlib import Path

from terminal.core.agent.loop import run_agent
from terminal.core.agent.protocol import AgentStep


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
    ) -> None:
        self.steps: list[AgentStep] = []
        self.answer = ""
        self.error = ""
        self.cancelled = False
        self.done = False

        self._task = task
        self._brain = brain
        self._root = root
        self._max_steps = max_steps
        self._stop = threading.Event()

        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Просит цикл остановиться после текущего шага."""

        self._stop.set()

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
            )

            self.answer = result.answer
            self.error = result.error
            self.cancelled = result.cancelled

            if not self.steps and result.steps:
                self.steps = list(result.steps)
        except Exception as error:  # noqa: BLE001 — покажем в окне
            self.error = f"{type(error).__name__}: {error}"
        finally:
            self.done = True
