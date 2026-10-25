# Giperion/tests/test_agent_tasks.py                                 v001
# Состояние задач агента: сохранение, список, история и продолжение.

import json
import time

from terminal.core.agent import tasks
from terminal.core.agent.protocol import (
    AgentStep,
    ToolCall,
    ToolResult,
)
from terminal.ui.agent_job import AgentJob


class ScriptedBrain:
    def __init__(self, answers):
        self.answers = list(answers)

    def decide(self, prompt: str) -> str:
        return self.answers.pop(0)


def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout

    while time.time() < deadline:
        if predicate():
            return

        time.sleep(0.02)

    raise AssertionError("Не дождались состояния")


def test_state_roundtrip(tmp_path, monkeypatch) -> None:
    """Состояние сохраняется, читается и удаляется."""

    monkeypatch.setattr(tasks, "TASKS_DIR", tmp_path / "tasks")

    task_id = tasks.new_task_id()
    state = {
        "id": task_id,
        "task": "проверка",
        "status": tasks.STATUS_RUNNING,
        "steps": [],
        "history": [],
    }

    tasks.save_state(state)

    loaded = tasks.load_state(task_id)
    assert loaded is not None
    assert loaded["task"] == "проверка"
    assert loaded["updated_at"]

    assert [item["id"] for item in tasks.list_states()] == [task_id]

    tasks.remove_state(task_id)
    assert tasks.load_state(task_id) is None


def test_history_roundtrip() -> None:
    """История вызовов переживает JSON."""

    history = [
        (
            ToolCall("read_file", {"path": "a.txt"}),
            ToolResult(True, "альфа"),
        )
    ]

    data = json.loads(
        json.dumps(tasks.serialize_history(history))
    )
    restored = tasks.deserialize_history(data)

    assert restored[0][0].tool == "read_file"
    assert restored[0][1].text == "альфа"


def test_steps_roundtrip() -> None:
    """Шаги трейса восстанавливаются."""

    steps = [AgentStep(1, "tool", "read_file", "деталь")]
    restored = tasks.deserialize_steps(
        json.loads(json.dumps(tasks.serialize_steps(steps)))
    )

    assert restored[0].title == "read_file"


def test_job_saves_completed_state(tmp_path, monkeypatch) -> None:
    """После прогона задача помечается done и хранит историю."""

    monkeypatch.setattr(tasks, "TASKS_DIR", tmp_path / "tasks")

    brain = ScriptedBrain(
        [
            json.dumps(
                {"action": "answer", "text": "готово"},
                ensure_ascii=False,
            )
        ]
    )

    job = AgentJob(
        "задача",
        brain,
        tmp_path,
        max_steps=2,
        model_name="Тест",
        initial_history=[
            (
                ToolCall("read_file", {"path": "a"}),
                ToolResult(True, "x"),
            )
        ],
        persist=True,
    )

    _wait_for(lambda: job.done)

    state = tasks.load_state(job.task_id)

    assert state is not None
    assert state["status"] == tasks.STATUS_DONE
    assert state["answer"] == "готово"
    assert state["history"]


def test_resume_uses_saved_history(tmp_path, monkeypatch) -> None:
    """Продолжение получает историю и не делает заземление."""

    monkeypatch.setattr(tasks, "TASKS_DIR", tmp_path / "tasks")

    history = [
        (ToolCall("read_file", {"path": "a"}), ToolResult(True, "x"))
    ]

    brain = ScriptedBrain(
        [
            json.dumps(
                {"action": "answer", "text": "продолжил"},
                ensure_ascii=False,
            )
        ]
    )

    job = AgentJob(
        "задача",
        brain,
        tmp_path,
        max_steps=2,
        initial_history=history,
        persist=False,
    )

    _wait_for(lambda: job.done)

    assert job.answer == "продолжил"
    assert len(job.steps) == 1
