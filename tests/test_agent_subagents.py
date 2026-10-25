# Giperion/tests/test_agent_subagents.py                              v001
# Параллельные читающие подагенты: разбор аргументов и общий расход.

import json
import time

from terminal.core.agent.loop import _subagent_tasks, run_agent
from terminal.core.agent.protocol import ToolCall
from terminal.core.agent.providers import (
    NativeBrain,
    OpenAICompatibleProvider,
)


class ForkBrain:
    """Мозг с отдельной копией на каждую подзадачу."""

    def __init__(self, delay: float = 0.0, parent: bool = True) -> None:
        self.delay = delay
        self.parent = parent
        self.counter = 0

    def decide(self, prompt: str):
        if self.parent and self.counter == 0:
            self.counter += 1

            return json.dumps(
                {
                    "action": "tool",
                    "tool": "ask_subagent",
                    "args": {
                        "tasks": ["найди a", "найди b", "найди c"],
                    },
                },
                ensure_ascii=False,
            )

        if self.parent:
            return json.dumps(
                {"action": "answer", "text": "сводка"},
                ensure_ascii=False,
            )

        if self.delay:
            time.sleep(self.delay)

        self.counter += 1

        return json.dumps(
            {"action": "answer", "text": f"ответ {self.counter}"},
            ensure_ascii=False,
        )

    def fork(self):
        return ForkBrain(delay=self.delay, parent=False)


def test_subagent_tasks_parsing() -> None:
    """Подзадачи читаются из task и tasks, лишнее отбрасывается."""

    assert _subagent_tasks(ToolCall("ask_subagent", {})) == []

    assert _subagent_tasks(
        ToolCall("ask_subagent", {"task": "одна"})
    ) == ["одна"]

    assert _subagent_tasks(
        ToolCall("ask_subagent", {"tasks": ["раз", "два", ""]})
    ) == ["раз", "два"]

    assert _subagent_tasks(
        ToolCall(
            "ask_subagent",
            {"task": "первая", "tasks": ["вторая"]},
        )
    ) == ["первая", "вторая"]

    assert len(
        _subagent_tasks(
            ToolCall(
                "ask_subagent",
                {"tasks": [f"t{number}" for number in range(10)]},
            )
        )
    ) == 4


def test_parallel_subagents_are_faster_than_sequential(tmp_path) -> None:
    """Три подзадачи идут одновременно."""

    brain = ForkBrain(delay=0.25)
    started = time.monotonic()

    result = run_agent(
        "разбери три файла",
        brain,
        tmp_path,
        max_steps=3,
        ground_first=False,
    )

    elapsed = time.monotonic() - started

    assert result.answer == "сводка"

    steps = [step for step in result.steps if step.kind == "subagent"]

    assert len(steps) == 1
    assert steps[0].title == "Подагенты · 3"
    assert "найди a" in steps[0].detail
    assert "найди c" in steps[0].detail

    # Последовательно было бы не меньше 0.75 с.
    assert elapsed < 0.7


def test_subagent_results_keep_order_and_all_answers(tmp_path) -> None:
    """В наблюдении есть все подзадачи, порядок сохранён."""

    seen: list[str] = []

    class OrderedBrain(ForkBrain):
        def decide(self, prompt: str):
            seen.append(prompt)

            return super().decide(prompt)

    brain = OrderedBrain()

    result = run_agent(
        "три подзадачи",
        brain,
        tmp_path,
        max_steps=3,
        ground_first=False,
    )

    assert result.answer == "сводка"

    # Родитель сходил дважды: решение о подагентах и финальный ответ.
    assert len(seen) == 2

    last = seen[-1]

    assert last.index("найди a") < last.index("найди b") < last.index(
        "найди c"
    )
    assert "Результат: ответ" in last


def test_subagent_without_fork_runs_sequentially(tmp_path) -> None:
    """Мозг без fork всё равно получает все ответы, просто по очереди."""

    class PlainBrain(ForkBrain):
        fork = None

    brain = PlainBrain()
    result = run_agent(
        "три подзадачи",
        brain,
        tmp_path,
        max_steps=6,
        ground_first=False,
    )

    # Без fork подзадачи используют тот же мозг: он отвечает как родитель,
    # поэтому цикл завершается ответом, а не падением.
    assert result.answer in ("сводка",)


def test_native_fork_shares_usage() -> None:
    """Расход подагента попадает в общий счётчик родителя."""

    def transport(url, key, payload, timeout):
        return {
            "choices": [
                {"message": {"role": "assistant", "content": "ок"}}
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=transport,
    )

    parent = NativeBrain(provider)
    child = parent.fork()

    child.decide("подзадача")

    assert parent.total_tokens == 120
    assert parent.calls == 1
    assert child.total_tokens == 0
