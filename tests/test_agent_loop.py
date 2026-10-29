# Giperion/tests/test_agent_loop.py                                  v001
# Цикл агента: шаги, ошибки, лимит и отмена.

import json
import time

from terminal.core.agent import registry
from terminal.core.agent.context import (
    DecisionError,
    parse_decision,
)
from terminal.core.agent.loop import run_agent
from terminal.core.agent.protocol import ApprovalResult


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


def test_answer_without_read_is_rejected_every_time(tmp_path) -> None:
    """Псевдо-вызов policy не обходит требование реального чтения."""

    brain = ScriptedBrain(
        [
            _answer("ответ без чтения"),
            _answer("ещё один ответ без чтения"),
        ]
    )

    result = run_agent(
        "посмотри проект",
        brain,
        tmp_path,
        max_steps=2,
        ground_first=False,
        require_tool_first=True,
    )

    assert result.answer == ""
    assert "лимит" in result.error.lower()
    assert [step.title for step in result.steps] == [
        "Нужен шаг чтения",
        "Нужен шаг чтения",
    ]
    assert any("Сначала вызови" in prompt for prompt in brain.prompts)


def test_last_step_note_does_not_promise_skipped_tools(tmp_path) -> None:
    """Промпт последнего шага честно описывает выполнение инструмента."""

    brain = ScriptedBrain([_tool("list_dir", path=".")])

    run_agent(
        "посмотри проект",
        brain,
        tmp_path,
        max_steps=1,
        ground_first=False,
        require_tool_first=False,
    )

    assert "Если вернёшь вызов инструмента" in brain.prompts[0]
    assert "больше не выполняются" not in brain.prompts[0]


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
        "find_symbol": "read",
        "find_relevant": "read",
        "lsp_diagnostics": "read",
        "lsp_definition": "read",
        "lsp_references": "read",
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
        "remember": "write",
        "update_plan": "read",
        "fetch_url": "exec",
        "browser_read": "exec",
        "browser_act": "exec",
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


def test_context_budget_compacts_history() -> None:
    """Старые шаги сжимаются и промпт укладывается в бюджет."""

    from terminal.core.agent.context import build_prompt
    from terminal.core.agent.protocol import ToolCall, ToolResult

    history = [
        (
            ToolCall("read_file", {"path": f"file{index}.txt"}),
            ToolResult(True, "строка\n" * 400),
        )
        for index in range(20)
    ]

    prompt = build_prompt("задача", history, max_chars=8000)

    assert len(prompt) <= 8000
    assert "Ранее:" in prompt or "сжаты" in prompt


def test_loop_stops_when_budget_too_small(tmp_path) -> None:
    """Если даже системный промпт не влезает — понятная ошибка."""

    brain = ScriptedBrain([_answer("не дойдёт")])

    result = run_agent(
        "задача",
        brain,
        tmp_path,
        ground_first=False,
        max_prompt_chars=200,
    )

    assert "бюджет" in result.error.lower()
    assert result.context_chars > 0


def test_result_reports_context_size(tmp_path) -> None:
    """Итог содержит пиковый размер контекста."""

    (tmp_path / "a.txt").write_text("альфа", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool("read_file", path="a.txt"),
            _answer("готово"),
        ]
    )

    result = run_agent(
        "прочитай",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.context_chars > 0


def test_trust_policy_applies_write_without_question(tmp_path) -> None:
    """Политика «доверять правкам» применяет патч без подтверждения."""

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
        "замени",
        brain,
        tmp_path,
        ground_first=False,
        policy="trust",
    )

    assert target.read_text(encoding="utf-8") == "новое"
    assert result.answer == "готово"
    assert any(
        "Разрешено политикой" in step.title
        for step in result.steps
    )


def test_read_policy_denies_write(tmp_path) -> None:
    """Политика «только чтение» не даёт менять файлы."""

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
            _answer("нельзя"),
        ]
    )

    result = run_agent(
        "замени",
        brain,
        tmp_path,
        ground_first=False,
        policy="read",
        approve=lambda request: True,
    )

    assert target.read_text(encoding="utf-8") == "старое"
    assert result.answer == "нельзя"
    assert any(
        "Запрещено политикой" in step.title
        for step in result.steps
    )


def test_trust_policy_still_asks_for_commands(tmp_path) -> None:
    """Даже в доверенном режиме команда требует подтверждения."""

    brain = ScriptedBrain(
        [
            _tool("run_command", command="git status"),
            _answer("ок"),
        ]
    )

    requests = []

    run_agent(
        "статус",
        brain,
        tmp_path,
        ground_first=False,
        policy="trust",
        approve=lambda request: requests.append(request) or False,
    )

    assert requests
    assert requests[0].title == "Выполнить команду"


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


class NativeBrainStub:
    """Мозг с настоящими вызовами и итогом без инструментов."""

    native = True

    def __init__(self, decisions, summary: str = "") -> None:
        self.decisions = list(decisions)
        self.prompts: list[str] = []
        self.summary = summary

    def decide(self, prompt: str):
        self.prompts.append(prompt)

        if not self.decisions:
            raise AssertionError("Сценарий кончился раньше времени")

        return self.decisions.pop(0)

    def summarize(self, prompt: str) -> str:
        self.prompts.append(prompt)

        return self.summary


def test_native_prompt_has_no_json_protocol(tmp_path) -> None:
    """Модель с tool calls не получает инструкцию про JSON."""

    from terminal.core.agent.protocol import AgentDecision, ToolCall

    brain = NativeBrainStub(
        [
            AgentDecision(
                action="tools",
                calls=(ToolCall("list_dir", {"path": "."}),),
            ),
            AgentDecision(action="answer", text="готово"),
        ]
    )

    result = run_agent(
        "посмотри проект",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.answer == "готово"
    assert '"action"' not in brain.prompts[0]
    assert "function calling" in brain.prompts[0]


def test_repeated_call_is_refused_with_previous_result(tmp_path) -> None:
    """Повтор того же вызова не выполняется, но отдаёт старый результат."""

    (tmp_path / "a.txt").write_text("альфа", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool("read_file", path="a.txt"),
            _tool("read_file", path="a.txt"),
            _answer("хватит"),
        ]
    )

    result = run_agent(
        "прочитай a.txt",
        brain,
        tmp_path,
        ground_first=False,
    )

    titles = [step.title for step in result.steps]

    assert "Повтор вызова" in titles
    assert result.answer == "хватит"

    repeated = next(
        step for step in result.steps if step.title == "Повтор вызова"
    )

    assert "альфа" in repeated.detail or "уже было" in repeated.detail


def test_step_limit_asks_for_summary(tmp_path) -> None:
    """Когда шаги кончились, модель просят подвести итог."""
    from terminal.core.agent.protocol import AgentDecision, ToolCall

    brain = NativeBrainStub(
        [
            AgentDecision(
                action="tools",
                calls=(ToolCall("list_dir", {"path": "."}),),
            )
        ],
        summary="прочитал только корень",
    )

    result = run_agent(
        "посмотри проект",
        brain,
        tmp_path,
        max_steps=1,
        ground_first=False,
    )

    assert result.answer == "прочитал только корень"
    assert result.error == ""
    assert result.steps[-1].kind == "answer"
    assert "Шаги закончились" in brain.prompts[-1]


def test_remembered_approval_skips_second_question(tmp_path) -> None:
    """«Не спрашивать» избавляет от повторного вопроса для того же файла."""

    from terminal.core.agent.protocol import ApprovalResult

    target = tmp_path / "a.txt"
    target.write_text("альфа\nбета\n", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool("apply_patch", path="a.txt", old="альфа", new="гамма"),
            _tool("apply_patch", path="a.txt", old="бета", new="дельта"),
            _answer("готово"),
        ]
    )

    asked: list[str] = []

    def approve(request) -> ApprovalResult:
        asked.append(request.key)

        return ApprovalResult(True, None, True)

    result = run_agent(
        "правь файл",
        brain,
        tmp_path,
        ground_first=False,
        approve=approve,
    )

    assert asked == ["file:a.txt"]
    assert target.read_text(encoding="utf-8") == "гамма\nдельта\n"
    assert result.answer == "готово"

    titles = [step.title for step in result.steps]
    assert any(
        title.startswith("Разрешено до конца задачи")
        for title in titles
    )
    assert any(title.startswith("Без вопроса") for title in titles)


def test_allowlist_is_per_file(tmp_path) -> None:
    """Разрешение одного файла не открывает другие."""

    from terminal.core.agent.protocol import ApprovalResult

    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("альфа\n", encoding="utf-8")
    second.write_text("бета\n", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool("apply_patch", path="a.txt", old="альфа", new="гамма"),
            _tool("apply_patch", path="b.txt", old="бета", new="дельта"),
            _answer("готово"),
        ]
    )

    asked: list[str] = []

    def approve(request) -> ApprovalResult:
        asked.append(request.key)

        return ApprovalResult(True, None, True)

    run_agent(
        "правь два файла",
        brain,
        tmp_path,
        ground_first=False,
        approve=approve,
    )

    assert asked == ["file:a.txt", "file:b.txt"]


def test_rejected_action_is_not_remembered(tmp_path) -> None:
    """Отклонённое действие не попадает в разрешённые."""

    from terminal.core.agent.protocol import ApprovalResult

    target = tmp_path / "a.txt"
    target.write_text("альфа\n", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool("apply_patch", path="a.txt", old="альфа", new="гамма"),
            _answer("ладно"),
        ]
    )

    asked = 0

    def approve(request) -> ApprovalResult:
        nonlocal asked
        asked += 1

        return ApprovalResult(False, None, True)

    result = run_agent(
        "правь файл",
        brain,
        tmp_path,
        ground_first=False,
        approve=approve,
    )

    assert asked == 1
    assert target.read_text(encoding="utf-8") == "альфа\n"
    assert result.answer == "ладно"


def test_preset_allowlist_skips_question(tmp_path) -> None:
    """Разрешение, переданное снаружи, действует с первого шага."""

    target = tmp_path / "a.txt"
    target.write_text("альфа\n", encoding="utf-8")

    brain = ScriptedBrain(
        [
            _tool("apply_patch", path="a.txt", old="альфа", new="гамма"),
            _answer("готово"),
        ]
    )

    def approve(request) -> bool:
        raise AssertionError("Спрашивать не должны")

    allowed = {"file:a.txt"}

    result = run_agent(
        "правь файл",
        brain,
        tmp_path,
        ground_first=False,
        approve=approve,
        allowed=allowed,
    )

    assert result.answer == "готово"
    assert "гамма" in target.read_text(encoding="utf-8")
    assert allowed == {"file:a.txt"}


def test_approval_key_for_commands_and_tests() -> None:
    """Ключ действия учитывает команду, тесты и файл."""

    from terminal.core.agent.loop import approval_key
    from terminal.core.agent.protocol import ToolCall

    assert approval_key(
        ToolCall("run_command", {"command": "git status"})
    ) == "command:git status"
    assert approval_key(ToolCall("run_tests", {})) == "run_tests"
    assert approval_key(
        ToolCall("apply_patch", {"path": "a.txt"})
    ) == "file:a.txt"

    # Коммит и откат не разрешаются оптом.
    assert approval_key(ToolCall("git_commit", {"message": "x"})) == ""
    assert approval_key(ToolCall("git_restore", {"path": "a.txt"})) == ""

def test_step_timeout_stops_task(tmp_path) -> None:
    """Модель, задумавшаяся дольше лимита, останавливает задачу."""

    class SlowBrain:
        def decide(self, prompt: str) -> str:
            time.sleep(1.0)

            return json.dumps(
                {"action": "answer", "text": "поздно"},
                ensure_ascii=False,
            )

    started = time.monotonic()

    result = run_agent(
        "задача",
        SlowBrain(),
        tmp_path,
        ground_first=False,
        require_tool_first=False,
        step_timeout=0.2,
    )

    elapsed = time.monotonic() - started

    assert "не ответила" in result.error
    assert elapsed < 0.8
    assert any(step.title == "Таймаут шага" for step in result.steps)

def test_grounding_adds_semantic_for_questions(tmp_path, monkeypatch) -> None:
    """Вопросы о проекте начинаются с find_relevant."""

    from terminal.core.agent import loop_helpers, settings

    monkeypatch.setattr(settings, "semantic_enabled", lambda: True)

    calls = loop_helpers.grounding_calls(
        "Где проверяются подтверждения записи файлов?",
        tmp_path,
    )

    assert any(call.tool == "find_relevant" for call in calls)

    create = loop_helpers.grounding_calls(
        "Создай файл eval.txt с текстом",
        tmp_path,
    )

    assert not any(call.tool == "find_relevant" for call in create)

    monkeypatch.setattr(settings, "semantic_enabled", lambda: False)

    disabled = loop_helpers.grounding_calls(
        "Где проверяются подтверждения?",
        tmp_path,
    )

    assert not any(call.tool == "find_relevant" for call in disabled)


def test_batch_approval_skips_later_writes(tmp_path) -> None:
    """Одна галочка «все правки» закрывает последующие записи."""

    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    brain = ScriptedBrain(
        [
            _tool("write_file", path="a.txt", content="A"),
            _tool("write_file", path="b.txt", content="B"),
            _answer("готово"),
        ]
    )
    calls = []

    def approve(request):
        calls.append(request.kind)

        return ApprovalResult(True, None, False, True)

    result = run_agent(
        "правь",
        brain,
        tmp_path,
        ground_first=False,
        require_tool_first=False,
        policy="confirm",
        approve=approve,
    )

    assert not result.error
    assert calls == ["write_file"]
    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "A"
    assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "B"


def test_plan_source_is_applied(tmp_path) -> None:
    """Ручная правка плана попадает в трейс и историю."""

    brain = ScriptedBrain([_answer("готово")])
    updates = [
        [
            {"text": "проверить", "status": "doing"},
            {"text": "ответить", "status": "pending"},
        ]
    ]

    result = run_agent(
        "ответь",
        brain,
        tmp_path,
        ground_first=False,
        require_tool_first=False,
        plan_source=lambda: updates.pop() if updates else None,
    )

    assert result.answer == "готово"
    assert any(step.kind == "plan" for step in result.steps)
    assert any(
        "проверить" in step.detail
        for step in result.steps
        if step.kind == "plan"
    )


def test_trust_still_shows_diff(tmp_path) -> None:
    """Политика trust не скрывает дифф записи."""

    (tmp_path / "a.txt").write_text("старое", encoding="utf-8")
    brain = ScriptedBrain(
        [
            _tool("write_file", path="a.txt", content="новое"),
            _answer("готово"),
        ]
    )

    result = run_agent(
        "правь",
        brain,
        tmp_path,
        ground_first=False,
        require_tool_first=False,
        policy="trust",
    )

    approvals = [step for step in result.steps if step.kind == "approval"]

    assert approvals
    assert "--- a/a.txt" in approvals[0].detail
    assert "+++ b/a.txt" in approvals[0].detail


def test_retryable_error_repeats_step(tmp_path) -> None:
    """Временная ошибка модели приводит к повтору шага."""

    from terminal.core.agent.errors import RetryableError

    class RetryBrain:
        def __init__(self) -> None:
            self.calls = 0

        def decide(self, prompt: str) -> str:
            self.calls += 1

            if self.calls == 1:
                raise RetryableError("временный сбой")

            return _answer("готово")

    brain = RetryBrain()
    result = run_agent(
        "ответь",
        brain,
        tmp_path,
        ground_first=False,
        require_tool_first=False,
    )

    assert result.answer == "готово"
    assert brain.calls == 2
    assert any(step.kind == "retry" for step in result.steps)
