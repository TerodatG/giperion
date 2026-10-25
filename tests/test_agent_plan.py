# Giperion/tests/test_agent_plan.py                                   v001
# План задачи: инструмент update_plan, чек-лист и статусы.

import json

from terminal.core.agent import registry
from terminal.core.agent.loop import render_plan, run_agent
from terminal.core.agent.protocol import ToolCall
from terminal.core.agent.providers import (
    NativeBrain,
    OpenAICompatibleProvider,
)


class ScriptedBrain:
    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []

    def decide(self, prompt: str) -> str:
        self.prompts.append(prompt)

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


def _plan(*steps: tuple[str, str]) -> list[dict]:
    return [
        {"text": text, "status": status}
        for text, status in steps
    ]


def test_render_plan_marks_statuses() -> None:
    """Чек-лист показывает выполненные, текущие и ожидающие пункты."""

    text = render_plan(
        [
            {"text": "прочитать", "status": "done"},
            {"text": "исправить", "status": "doing"},
            {"text": "проверить", "status": "pending"},
        ]
    )

    assert text.splitlines() == [
        "1. [x] прочитать",
        "2. [>] исправить",
        "3. [ ] проверить",
    ]


def test_plan_step_appears_in_trace(tmp_path) -> None:
    """Вызов update_plan даёт шаг plan и ответ модели."""

    brain = ScriptedBrain(
        [
            _tool(
                "update_plan",
                steps=_plan(
                    ("прочитать файл", "done"),
                    ("исправить", "doing"),
                    ("запустить тесты", "pending"),
                ),
            ),
            _answer("план принят"),
        ]
    )

    result = run_agent(
        "сложная задача",
        brain,
        tmp_path,
        ground_first=False,
        require_tool_first=True,
    )

    assert result.answer == "план принят"

    plans = [step for step in result.steps if step.kind == "plan"]

    assert len(plans) == 1
    assert "[x] прочитать файл" in plans[0].detail
    assert "[>] исправить" in plans[0].detail
    assert plans[0].title == "План · 3 пунктов"


def test_plan_normalizes_bad_items(tmp_path) -> None:
    """Неизвестный статус становится pending, пустые пункты выпадают."""

    brain = ScriptedBrain(
        [
            _tool(
                "update_plan",
                steps=[
                    {"text": "шаг", "status": "странный"},
                    {"text": "  ", "status": "pending"},
                    "мусор",
                ],
            ),
            _answer("ок"),
        ]
    )

    result = run_agent(
        "план",
        brain,
        tmp_path,
        ground_first=False,
    )

    plan = next(step for step in result.steps if step.kind == "plan")

    assert "[ ] шаг" in plan.detail
    assert "мусор" not in plan.detail


def test_empty_plan_is_an_error_observation(tmp_path) -> None:
    """Пустой план не ломает цикл и объясняет, что нужно."""

    brain = ScriptedBrain(
        [
            _tool("update_plan", steps=[]),
            _answer("без плана"),
        ]
    )

    result = run_agent(
        "план",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.answer == "без плана"
    assert not any(step.kind == "plan" for step in result.steps)


def test_plan_tool_schema_and_risk() -> None:
    """Схема описывает массив шагов, подтверждение не требуется."""

    spec = registry.get_spec("update_plan")

    assert spec is not None
    assert spec.risk == "read"
    assert spec.required == ("steps",)

    schema = next(
        item
        for item in registry.tool_schemas()
        if item["function"]["name"] == "update_plan"
    )
    steps = schema["function"]["parameters"]["properties"]["steps"]

    assert steps["type"] == "array"
    assert steps["items"]["properties"]["status"]["enum"] == [
        "pending",
        "doing",
        "done",
    ]

    assert not registry.needs_approval(
        ToolCall("update_plan", {"steps": [{"text": "x"}]})
    )

    assert registry.validate_call(
        ToolCall("update_plan", {"steps": []})
    ) is None


def test_plan_in_chat_mode(tmp_path) -> None:
    """В режиме переписки план тоже попадает в трейс и в tool-ответ."""

    calls: list[list] = []

    def reply_plan() -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_plan",
                                "type": "function",
                                "function": {
                                    "name": "update_plan",
                                    "arguments": json.dumps(
                                        {
                                            "steps": _plan(
                                                ("раз", "done"),
                                                ("два", "pending"),
                                            )
                                        }
                                    ),
                                },
                            }
                        ],
                    }
                }
            ]
        }

    replies = [
        reply_plan(),
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "готово",
                    }
                }
            ]
        },
    ]

    def transport(url, key, payload, timeout):
        calls.append(payload["messages"])

        return replies.pop(0)

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=transport,
    )
    brain = NativeBrain(provider)

    result = run_agent(
        "план",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.answer == "готово"

    plan = next(step for step in result.steps if step.kind == "plan")

    assert "[x] раз" in plan.detail

    tool = calls[1][-1]

    assert tool["role"] == "tool"
    assert tool["tool_call_id"] == "call_plan"
    assert "План обновлён" in tool["content"]
