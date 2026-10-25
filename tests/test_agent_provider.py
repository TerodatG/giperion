# Giperion/tests/test_agent_provider.py                              v001
# Провайдер с tool calls: разбор ответа и мозг без JSON-обёртки.

import json

import pytest

from terminal.core.agent.loop import run_agent
from terminal.core.agent.protocol import (
    AgentDecision,
    ToolCall,
)
from terminal.core.agent.providers import (
    NativeBrain,
    OpenAICompatibleProvider,
    ProviderError,
    provider_from_env,
)


def _transport_with_calls(url, key, payload, timeout):
    assert url.endswith("/chat/completions")
    assert key == "secret"
    assert payload["model"] == "test-model"
    assert payload["tools"]
    assert payload["tool_choice"] == "auto"

    return {
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "read_file",
                                "arguments": json.dumps(
                                    {"path": "a.txt"}
                                ),
                            }
                        }
                    ],
                }
            }
        ]
    }


def test_provider_parses_tool_calls() -> None:
    """OpenAI-совместимый ответ превращается в ToolCall."""

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=_transport_with_calls,
    )

    reply = provider.complete(
        [{"role": "user", "content": "привет"}],
        [{"type": "function", "function": {"name": "read_file"}}],
    )

    assert reply.text == ""
    assert reply.calls == (ToolCall("read_file", {"path": "a.txt"}),)


def test_native_brain_returns_decision() -> None:
    """Мозг отдаёт решение с несколькими вызовами без JSON-текста."""

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=_transport_with_calls,
    )

    decision = NativeBrain(provider).decide("прочитай a.txt")

    assert decision.action == "tools"
    assert decision.calls[0].tool == "read_file"


def test_provider_rejects_plain_answer() -> None:
    """Если tool_calls нет, но есть текст — это ответ."""

    def transport(url, key, payload, timeout):
        return {
            "choices": [
                {"message": {"content": "готово"}}
            ]
        }

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=transport,
    )

    decision = NativeBrain(provider).decide("задача")

    assert decision.action == "answer"
    assert decision.text == "готово"


def test_provider_rejects_bad_arguments() -> None:
    """Битые аргументы вызова — понятная ошибка."""

    def transport(url, key, payload, timeout):
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "read_file",
                                    "arguments": "{не json",
                                }
                            }
                        ]
                    }
                }
            ]
        }

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=transport,
    )

    with pytest.raises(ProviderError):
        provider.complete([{"role": "user", "content": "x"}], [])


def test_provider_from_env(monkeypatch) -> None:
    """Провайдер собирается только при полном наборе переменных."""

    monkeypatch.delenv("AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_MODEL", raising=False)

    assert provider_from_env() is None

    monkeypatch.setenv("AGENT_BASE_URL", "http://localhost/v1")
    monkeypatch.setenv("AGENT_API_KEY", "secret")
    monkeypatch.setenv("AGENT_MODEL", "test-model")

    provider = provider_from_env()

    assert provider is not None
    assert provider.model == "test-model"


class DecisionBrain:
    """Мозг, который сразу отдаёт готовые решения."""

    def __init__(self, decisions):
        self.decisions = list(decisions)

    def decide(self, prompt: str) -> AgentDecision:
        return self.decisions.pop(0)


def test_loop_accepts_native_decisions(tmp_path) -> None:
    """Цикл работает с решениями провайдера, а не только с JSON."""

    (tmp_path / "a.txt").write_text("альфа", encoding="utf-8")

    brain = DecisionBrain(
        [
            AgentDecision(
                action="tools",
                calls=(
                    ToolCall("read_file", {"path": "a.txt"}),
                ),
            ),
            AgentDecision(action="answer", text="прочитано"),
        ]
    )

    result = run_agent(
        "прочитай a.txt",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.answer == "прочитано"
    assert [step.kind for step in result.steps] == [
        "tool",
        "answer",
    ]
