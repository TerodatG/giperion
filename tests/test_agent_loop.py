# Giperion/tests/test_agent_loop.py                                  v001
# Цикл агента: шаги, ошибки, лимит и отмена.

import json

from terminal.core.agent import registry
from terminal.core.agent.context import (
    DecisionError,
    parse_decision,
)
from terminal.core.agent.loop import run_agent


class ScriptedBrain:
    """Отдаёт заранее заготовленные ответы по очереди."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def decide(self, prompt: str) -> str:
        self.prompts.append(prompt)

        if not self.answers:
            raise AssertionError("Сценарий кончился раньше времени")

        return self.answers.pop(0)


def _tool(name: str, **args) -> str:
    return json.dumps(
        {"action": "tool", "tool": name, "args": args},
        ensure_ascii=False,
    )


def _answer(text: str) -> str:
    return json.dumps(
        {"action": "answer", "text": text},
        ensure_ascii=False,
    )


def test_agent_reads_file_and_answers(tmp_path) -> None:
    """Агент делает шаг чтения и возвращает ответ."""

    (tmp_path / "a.txt").write_text("secret project", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool("read_file", path="a.txt"),
            _answer("В файле написан проект."),
        ]
    )

    result = run_agent(
        "что в a.txt",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.answer == "В файле написан проект."
    assert result.error == ""
    assert [step.kind for step in result.steps] == ["tool", "answer"]
    assert "read_file" in result.steps[0].title
    assert "a.txt" in result.steps[0].detail
    assert "a.txt" in brain.prompts[1]


def test_invalid_json_is_reported_and_retried(tmp_path) -> None:
    """Невалидный ответ становится наблюдением, цикл продолжается."""

    brain = ScriptedBrain(
        [
            "это не json",
            _answer("исправился"),
        ]
    )

    result = run_agent(
        "задача",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.answer == "исправился"
    assert result.steps[0].kind == "error"
    assert result.steps[0].title == "Некорректное решение"


def test_step_limit_stops_agent(tmp_path) -> None:
    """Лимит шагов не даёт циклу работать бесконечно."""

    brain = ScriptedBrain(
        [_tool("list_dir", path=".") for _ in range(3)]
    )

    result = run_agent(
        "задача",
        brain,
        tmp_path,
        max_steps=3,
        ground_first=False,
    )

    assert result.answer == ""
    assert "лимит" in result.error.lower()
    assert len(result.steps) == 3


def test_cancel_stops_before_next_step(tmp_path) -> None:
    """Отмена прекращает цикл между шагами."""

    calls = {"count": 0}

    def should_stop() -> bool:
        calls["count"] += 1

        return calls["count"] > 1

    brain = ScriptedBrain(
        [_tool("list_dir", path="."), _answer("не должно случиться")]
    )

    result = run_agent(
        "задача",
        brain,
        tmp_path,
        should_stop=should_stop,
        ground_first=False,
    )

    assert result.cancelled is True
    assert result.answer == ""


def test_registry_has_read_write_and_exec_tools() -> None:
    """В A2 есть чтение, запись и запуск тестов с разными рисками."""

    risks = {spec.name: spec.risk for spec in registry.TOOL_SPECS}

    assert risks == {
        "list_dir": "read",
        "read_file": "read",
        "search_text": "read",
        "apply_patch": "write",
        "write_file": "write",
        "run_tests": "exec",
    }


def test_unknown_tool_is_an_error_observation(tmp_path) -> None:
    """Неизвестный инструмент не роняет цикл."""

    brain = ScriptedBrain(
        [
            _tool("delete_file", path="a.txt"),
            _answer("нельзя"),
        ]
    )

    result = run_agent(
        "удали",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.answer == "нельзя"
    assert "Неизвестный инструмент" in result.steps[0].detail


def test_grounding_reads_named_file(tmp_path) -> None:
    """Первый шаг агента читает файл, названный в задаче."""

    (tmp_path / "README.md").write_text(
        "строка 1\nстрока 2\n",
        encoding="utf-8",
    )

    brain = ScriptedBrain([_answer("две строки")])

    result = run_agent(
        "сколько строк в README.md",
        brain,
        tmp_path,
    )

    assert result.steps[0].title.startswith("старт")
    assert "README.md" in result.steps[0].detail
    assert result.answer == "две строки"


def test_write_is_rejected_without_changes(tmp_path) -> None:
    """Отклонение не меняет файл и возвращает наблюдение агенту."""

    target = tmp_path / "a.txt"
    target.write_text("старое", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool(
                "apply_patch",
                path="a.txt",
                old="старое",
                new="новое",
            ),
            _answer("отменено"),
        ]
    )

    requests = []

    result = run_agent(
        "замени слово",
        brain,
        tmp_path,
        ground_first=False,
        approve=lambda request: requests.append(request) or False,
    )

    assert requests
    assert requests[0].title == "Изменить файл"
    assert "новое" in requests[0].detail
    assert target.read_text(encoding="utf-8") == "старое"
    assert any(step.kind == "approval" for step in result.steps)
    assert result.answer == "отменено"


def test_write_applies_after_approval(tmp_path) -> None:
    """Одобрение применяет патч и оставляет резервную копию."""

    target = tmp_path / "a.txt"
    target.write_text("старое", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool(
                "apply_patch",
                path="a.txt",
                old="старое",
                new="новое",
            ),
            _answer("готово"),
        ]
    )

    result = run_agent(
        "замени слово",
        brain,
        tmp_path,
        ground_first=False,
        approve=lambda request: True,
    )

    assert target.read_text(encoding="utf-8") == "новое"
    assert result.answer == "готово"
    assert (tmp_path / "data" / "agent_backups").is_dir()


def test_parse_decision_accepts_fenced_json() -> None:
    """JSON в ```-блоке тоже разбирается."""

    decision = parse_decision(
        '```json\n{"action": "answer", "text": "ок"}\n```'
    )

    assert decision.action == "answer"
    assert decision.text == "ок"


def test_parse_decision_rejects_garbage() -> None:
    """Мусор вместо решения — понятная ошибка."""

    try:
        parse_decision("просто текст")
    except DecisionError:
        pass
    else:
        raise AssertionError("Ожидалась DecisionError")
