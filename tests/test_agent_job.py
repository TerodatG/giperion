# Giperion/tests/test_agent_job.py                                   v001
# Фоновый запуск агента и ожидание подтверждения из окна.

import json
import time

from terminal.core.agent.loop import run_agent
from terminal.ui.agent_job import AgentJob


class ScriptedBrain:
    def __init__(self, answers: list[str]) -> None:
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


def test_job_waits_for_approval(tmp_path) -> None:
    """Поток агента ждёт кнопку и не пишет файл без согласия."""

    target = tmp_path / "a.txt"
    target.write_text("старое", encoding="utf-8")

    brain = ScriptedBrain(
        [
            json.dumps(
                {
                    "action": "tool",
                    "tool": "apply_patch",
                    "args": {
                        "path": "a.txt",
                        "old": "старое",
                        "new": "новое",
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {"action": "answer", "text": "отменено"},
                ensure_ascii=False,
            ),
        ]
    )

    job = AgentJob(
        "замени",
        brain,
        tmp_path,
        max_steps=4,
        persist=False,
    )

    _wait_for(lambda: job.pending is not None or job.done)

    assert job.pending is not None
    assert job.pending.title == "Изменить файл"

    job.resolve_approval(False)
    _wait_for(lambda: job.done)

    assert target.read_text(encoding="utf-8") == "старое"
    assert any(step.kind == "approval" for step in job.steps)


def test_job_writes_run_journal(tmp_path, monkeypatch) -> None:
    """После прогона в журнале появляется запись с шагами и временем."""

    import json as json_module

    from terminal.core.agent import runs

    journal = tmp_path / "agent_runs.jsonl"
    monkeypatch.setattr(runs, "RUNS_FILE", journal)

    (tmp_path / "a.txt").write_text("альфа", encoding="utf-8")

    brain = ScriptedBrain(
        [
            json_module.dumps(
                {
                    "action": "tool",
                    "tool": "read_file",
                    "args": {"path": "a.txt"},
                },
                ensure_ascii=False,
            ),
            json_module.dumps(
                {"action": "answer", "text": "готово"},
                ensure_ascii=False,
            ),
        ]
    )

    job = AgentJob(
        "прочитай",
        brain,
        tmp_path,
        max_steps=4,
        model_name="Тест",
        persist=False,
    )

    _wait_for(lambda: job.done)

    lines = journal.read_text(encoding="utf-8").splitlines()

    assert lines
    record = json_module.loads(lines[-1])
    assert record["model"] == "Тест"
    assert record["steps"] >= 1
    assert record["duration_s"] >= 0


def test_run_agent_without_approval_callback_denies_write(tmp_path) -> None:
    """Без callback запись считается отклонённой."""

    target = tmp_path / "a.txt"
    target.write_text("старое", encoding="utf-8")

    brain = ScriptedBrain(
        [
            json.dumps(
                {
                    "action": "tool",
                    "tool": "apply_patch",
                    "args": {
                        "path": "a.txt",
                        "old": "старое",
                        "new": "новое",
                    },
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {"action": "answer", "text": "без подтверждения нельзя"},
                ensure_ascii=False,
            ),
        ]
    )

    result = run_agent(
        "замени",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert target.read_text(encoding="utf-8") == "старое"
    assert result.answer == "без подтверждения нельзя"
