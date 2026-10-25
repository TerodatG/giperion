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
        "git_status": "read",
        "git_diff": "read",
        "git_log": "read",
        "git_commit": "write",
        "git_restore": "write",
        "run_command": "exec",
        "ask_subagent": "read",
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


def test_run_command_requires_approval(tmp_path) -> None:
    """Команда не выполняется без согласия пользователя."""

    brain = ScriptedBrain(
        [
            _tool("run_command", command="git status"),
            _answer("не разрешили"),
        ]
    )

    requests = []

    result = run_agent(
        "посмотри статус",
        brain,
        tmp_path,
        ground_first=False,
        approve=lambda request: requests.append(request) or False,
    )

    assert requests
    assert requests[0].title == "Выполнить команду"
    assert "status" in requests[0].detail
    assert result.answer == "не разрешили"


def test_subagent_answers_within_parent_task(tmp_path) -> None:
    """Подагент читает сам, родитель получает его ответ."""

    (tmp_path / "a.txt").write_text("альфа", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool("ask_subagent", task="что в a.txt"),
            _answer("внутри: альфа"),
            _answer("снаружи: альфа"),
        ]
    )

    result = run_agent(
        "узнай, что в a.txt",
        brain,
        tmp_path,
        max_steps=4,
        ground_first=False,
    )

    assert result.answer == "снаружи: альфа"
    assert any(step.kind == "subagent" for step in result.steps)
    assert "внутри: альфа" in result.steps[0].detail


def test_multiple_tools_in_one_step(tmp_path) -> None:
    """Модель может запросить несколько чтений за шаг."""

    (tmp_path / "a.txt").write_text("альфа", encoding="utf-8")
    (tmp_path / "b.txt").write_text("бета", encoding="utf-8")

    calls = {
        "action": "tools",
        "calls": [
            {"tool": "read_file", "args": {"path": "a.txt"}},
            {"tool": "read_file", "args": {"path": "b.txt"}},
        ],
    }

    brain = ScriptedBrain(
        [
            json.dumps(calls, ensure_ascii=False),
            _answer("прочитал оба"),
        ]
    )

    result = run_agent(
        "прочитай оба файла",
        brain,
        tmp_path,
        ground_first=False,
    )

    tool_steps = [
        step for step in result.steps if step.kind == "tool"
    ]

    assert len(tool_steps) == 2
    assert result.answer == "прочитал оба"


def test_parse_decision_accepts_tools_list() -> None:
    """Формат tools с несколькими вызовами разбирается."""

    decision = parse_decision(
        '{"action": "tools", "calls": ['
        '{"tool": "read_file", "args": {"path": "a"}},'
        '{"tool": "read_file", "args": {"path": "b"}}]}'
    )

    assert decision.action == "tools"
    assert len(decision.calls) == 2


def test_schemas_require_arguments() -> None:
    """Схемы несут обязательные поля, а валидатор их проверяет."""

    schemas = {
        schema["function"]["name"]: schema
        for schema in registry.tool_schemas()
    }

    read_schema = schemas["read_file"]["function"]["parameters"]

    assert read_schema["required"] == ["path"]
    assert "path" in read_schema["properties"]

    missing = registry.validate_call(
        registry.ToolCall(tool="read_file", args={})
    )
    extra = registry.validate_call(
        registry.ToolCall(
            tool="read_file",
            args={"path": "a.txt", "line": "1"},
        )
    )

    assert missing is not None and not missing.ok
    assert extra is not None and not extra.ok


def test_approval_can_edit_text(tmp_path) -> None:
    """Пользователь может применить свой текст вместо патча агента."""

    from terminal.core.agent.protocol import ApprovalResult

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
            _answer("применено"),
        ]
    )

    result = run_agent(
        "замени",
        brain,
        tmp_path,
        ground_first=False,
        approve=lambda request: ApprovalResult(
            True,
            "исправлено пользователем\n",
        ),
    )

    assert result.answer == "применено"
    assert target.read_text(encoding="utf-8") == (
        "исправлено пользователем\n"
    )


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
