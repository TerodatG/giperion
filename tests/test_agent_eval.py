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


def test_fatal_provider_errors() -> None:
    """Исчерпание квоты и отказ ключа останавливают прогон."""

    assert eval_agent.is_fatal(
        "Модель сообщила об ошибке: Free usage limit reached."
    )
    assert eval_agent.is_fatal("Провайдер отклонил ключ (401)")
    assert eval_agent.is_fatal("insufficient funds")

    assert not eval_agent.is_fatal("")
    assert not eval_agent.is_fatal("достигнут лимит шагов")
    assert not eval_agent.is_fatal("тесты упали: 3 failed")


def test_summarize_stability() -> None:
    """Повторы дают стабильные, плавающие и падающие задачи."""

    def item(task_id, attempt, ok):
        return {
            "id": task_id,
            "ok": ok,
            "steps": 3,
            "duration_s": 2.0,
            "context_chars": 100,
            "attempt": attempt,
        }

    summary = eval_agent.summarize(
        [
            item("stable", 1, True),
            item("stable", 2, True),
            item("flaky", 1, False),
            item("flaky", 2, True),
            item("broken", 1, False),
            item("broken", 2, False),
        ]
    )

    assert summary["runs"] == 2
    assert summary["stable_tasks"] == 1
    assert summary["flaky_tasks"] == 1
    assert summary["per_task"]["stable"]["passed"] == 2
    assert summary["per_task"]["flaky"]["passed"] == 1
    assert summary["per_task"]["broken"]["passed"] == 0


def test_regression_note_respects_threshold() -> None:
    """Регрессия замечается только при падении сильнее порога."""

    previous = {
        "success_rate": 1.0,
        "total": 16,
        "task_ids": ["a", "b"],
    }
    summary = {
        "success_rate": 0.8,
        "total": 16,
        "task_ids": ["a", "b"],
    }

    assert "РЕГРЕССИЯ" in eval_agent.regression_note(
        previous, summary, 10
    )
    assert eval_agent.regression_note(previous, summary, 25) == ""
    assert eval_agent.regression_note({}, summary, 10) == ""
    assert eval_agent.regression_note(
        previous,
        {"success_rate": 1.0, "total": 16, "task_ids": ["a", "b"]},
        10,
    ) == ""


def test_regression_skips_other_task_set() -> None:
    """Разные наборы задач не сравниваются."""

    previous = {
        "success_rate": 1.0,
        "total": 16,
        "task_ids": ["a", "b"],
    }
    summary = {
        "success_rate": 0.5,
        "total": 4,
        "task_ids": ["a"],
    }

    assert eval_agent.regression_note(previous, summary, 10) == ""


def test_history_roundtrip(tmp_path, monkeypatch) -> None:
    """История прогонов пишется и читается."""

    from tools import eval_report

    monkeypatch.setattr(
        eval_report,
        "HISTORY",
        tmp_path / "history.jsonl",
    )

    summary = eval_agent.summarize(
        [
            {
                "id": "a",
                "ok": True,
                "steps": 2,
                "duration_s": 1.0,
                "context_chars": 50,
                "attempt": 1,
            }
        ]
    )

    eval_agent.append_history("test-model", summary)

    records = eval_agent.read_history(5)

    assert len(records) == 1
    assert records[0]["model"] == "test-model"
    assert records[0]["passed"] == 1
    assert records[0]["runs"] == 1


def test_history_empty(tmp_path, monkeypatch) -> None:
    """Пустая история не падает."""

    from tools import eval_report

    monkeypatch.setattr(
        eval_report,
        "HISTORY",
        tmp_path / "missing.jsonl",
    )

    assert eval_agent.read_history(5) == []


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

    from tools import eval_runner

    monkeypatch.setattr(
        eval_runner,
        "create_worktree",
        lambda base, name: (worktree, "agent/stub"),
    )
    monkeypatch.setattr(
        eval_runner,
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


def test_web_prepare_patches_and_restores(tmp_path) -> None:
    """Контекст веб-задачи подменяет сеть и возвращает всё назад."""

    from terminal.core.agent import settings, web

    old_get = web.HTTP_GET
    old_enabled = settings.browser_enabled

    with eval_agent._web_prepare("кипарис")(tmp_path):
        assert settings.browser_enabled() is True

        _url, content_type, body = web.HTTP_GET(
            "https://example.com/secret"
        )

        assert "text/html" in content_type
        assert "кипарис" in body.decode("utf-8")
        assert web.is_public_host("example.com") is True

    assert web.HTTP_GET is old_get
    assert settings.browser_enabled is old_enabled


def test_mcp_prepare_exposes_echo(tmp_path) -> None:
    """Контекст MCP-задачи поднимает стаб и убирает его после."""

    from terminal.core.agent import mcp, settings

    old_file = mcp.CONFIG_FILE

    with eval_agent._mcp_prepare()(tmp_path):
        assert settings.mcp_enabled() is True

        specs = {spec.name for spec in mcp.mcp_tools()[0]}

        assert "mcp_stub_echo" in specs

        server = mcp.load_servers()[0]

        with mcp.McpClient(server, timeout=10) as client:
            result = client.call_tool("echo", {"text": "тест"})

        assert result.ok
        assert result.text == "эхо: тест"

    assert mcp.CONFIG_FILE is old_file


def test_plan_and_subagent_inspectors() -> None:
    """Проверки смотрят на шаги, а не только на ответ."""

    from types import SimpleNamespace

    from terminal.core.agent.protocol import AgentStep

    plan_result = SimpleNamespace(
        steps=[
            AgentStep(
                1,
                "plan",
                "План · 3 пунктов",
                "1. [ ] раз\n2. [ ] два\n3. [ ] три",
            )
        ],
        answer="MAX_PROMPT в context.py",
    )

    ok, note = eval_agent._plan_inspect(None, plan_result)
    assert ok
    assert "context.py" in note

    two_items = SimpleNamespace(
        steps=[
            AgentStep(1, "plan", "План · 2 пунктов", "1. [ ] раз\n2. [ ] два")
        ],
        answer="context.py",
    )

    ok, _note = eval_agent._plan_inspect(None, two_items)
    assert not ok

    subagents = SimpleNamespace(
        steps=[
            AgentStep(
                1,
                "subagent",
                "Подагенты · 2",
                "Задача: a\nРезультат: x",
            )
        ],
        answer="providers.py и budget.py",
    )

    ok, note = eval_agent._subagents_inspect(None, subagents)
    assert ok
    assert "оба" in note

    subagents.answer = "только providers.py"
    ok, _note = eval_agent._subagents_inspect(None, subagents)
    assert not ok


def test_run_task_uses_prepare_and_inspect(tmp_path, monkeypatch) -> None:
    """run_task включает контекст и проверяет по результату."""

    worktree = tmp_path / "wt"
    worktree.mkdir()
    (worktree / "flag.txt").write_text("нет", encoding="utf-8")

    from tools import eval_runner

    monkeypatch.setattr(
        eval_runner,
        "create_worktree",
        lambda base, name: (worktree, "agent/stub"),
    )
    monkeypatch.setattr(
        eval_runner,
        "remove_worktree",
        lambda *args, **kwargs: "ок",
    )

    seen: dict = {}

    def prepare(folder):
        from contextlib import contextmanager

        @contextmanager
        def context():
            seen["inside"] = True

            try:
                yield
            finally:
                seen["after"] = True

        return context()

    def inspect(folder, result):
        return (
            bool(seen.get("inside")),
            "контекст был включён" if seen.get("inside") else "нет контекста",
        )

    task = eval_agent.EvalTask(
        "with-context",
        "Контекст",
        "скажи",
        eval_agent.answer_has("готово"),
        max_steps=2,
        inspect=inspect,
        prepare=prepare,
    )

    brain = ScriptedBrain(
        [AgentDecision(action="answer", text="готово")]
    )

    result = eval_agent.run_task(task, brain, tmp_path)

    assert result["ok"] is True
    assert seen.get("after") is True


def test_report_roundtrip(tmp_path, monkeypatch) -> None:
    """Отчёт сохраняется и читается как предыдущий."""

    output = tmp_path / "eval"
    latest = output / "latest.json"

    from tools import eval_report

    monkeypatch.setattr(eval_report, "OUTPUT_DIR", output)
    monkeypatch.setattr(eval_report, "LATEST", latest)

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
