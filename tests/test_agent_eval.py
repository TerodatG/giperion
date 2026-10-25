# Giperion/tests/test_agent_eval.py                                  v001
# Стенд оценки агента: проверки, сводка и запуск задачи без git.

import json

from terminal.core.agent.protocol import AgentDecision

from tools import eval_agent


class ScriptedBrain:
    def __init__(self, answers):
        self.answers = list(answers)

    def decide(self, prompt: str) -> AgentDecision:
        return self.answers.pop(0)


def test_answer_check() -> None:
    check = eval_agent.answer_has("model_catalog.py")

    ok, note = check(None, "Функция лежит в model_catalog.py")

    assert ok
    assert "model_catalog.py" in note

    ok, note = check(None, "не знаю")

    assert not ok


def test_file_checks(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("Привет", encoding="utf-8")

    assert eval_agent.file_has("a.txt", "привет")(tmp_path, "")[0]
    assert eval_agent.file_equals("a.txt", "Привет")(tmp_path, "")[0]
    assert not eval_agent.file_has("a.txt", "нет")(tmp_path, "")[0]


def test_readme_line_count(tmp_path) -> None:
    (tmp_path / "README.md").write_text("a\nb\nc\n", encoding="utf-8")

    check = eval_agent.readme_line_count()

    assert check(tmp_path, "в README 3 строки")[0]
    assert not check(tmp_path, "5 строк")[0]


def test_tests_passed_accepts_russian_answer() -> None:
    """Ответ про тесты засчитывается и по-русски."""

    check = eval_agent.tests_passed()

    for answer in (
        "Все 411 тестов пройдено успешно.",
        "Тесты прошли, код 0.",
        "7 passed in 12s",
        "Сборка зелёная, всё успешно.",
    ):
        ok, note = check(None, answer)

        assert ok, answer
        assert note

    ok, note = check(None, "Не удалось запустить тесты.")
    assert not ok
    assert note == "нет результата"


def test_summarize() -> None:
    results = [
        {"ok": True, "steps": 4, "duration_s": 2.0, "context_chars": 100},
        {"ok": False, "steps": 8, "duration_s": 4.0, "context_chars": 300},
    ]

    summary = eval_agent.summarize(results)

    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["avg_steps"] == 6.0
    assert summary["max_context"] == 300


def test_run_task_in_stub_worktree(tmp_path, monkeypatch) -> None:
    """Задача выполняется в подставном дереве, отчёт содержит метрики."""

    worktree = tmp_path / "wt"
    worktree.mkdir()

    monkeypatch.setattr(
        eval_agent,
        "create_worktree",
        lambda base, name: (worktree, "agent/stub"),
    )
    monkeypatch.setattr(
        eval_agent,
        "remove_worktree",
        lambda *args, **kwargs: "ок",
    )

    task = eval_agent.EvalTask(
        "stub",
        "Заглушка",
        "Скажи слово",
        eval_agent.answer_has("готово"),
        max_steps=2,
    )

    brain = ScriptedBrain(
        [AgentDecision(action="answer", text="готово")]
    )

    result = eval_agent.run_task(task, brain, tmp_path)

    assert result["ok"] is True
    assert result["steps"] >= 1
    assert result["context_chars"] > 0


def test_report_roundtrip(tmp_path, monkeypatch) -> None:
    """Отчёт сохраняется и читается как предыдущий."""

    output = tmp_path / "eval"
    latest = output / "latest.json"

    monkeypatch.setattr(eval_agent, "OUTPUT_DIR", output)
    monkeypatch.setattr(eval_agent, "LATEST", latest)

    summary = eval_agent.summarize(
        [
            {
                "ok": True,
                "steps": 2,
                "duration_s": 1.0,
                "context_chars": 50,
            }
        ]
    )

    path = eval_agent.save_report("test", [], summary)

    assert path.exists()
    assert json.loads(latest.read_text(encoding="utf-8"))[
        "summary"
    ]["passed"] == 1
    assert eval_agent.load_previous()["passed"] == 1
