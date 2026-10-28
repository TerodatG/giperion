# Giperion/tests/test_provider_anthropic.py                            v001
# Anthropic-провайдер, резервный провайдер и оценка стоимости.

import pytest

from terminal.core.agent.cost import estimate_cost, format_cost, price_for
from terminal.core.agent.provider_anthropic import (
    AnthropicProvider,
    to_anthropic_messages,
    to_anthropic_tools,
)
from terminal.core.agent.provider_http import ProviderError, ProviderReply
from terminal.core.agent.provider_router import FallbackProvider

REPLY = {
    "content": [
        {"type": "text", "text": "Готово."},
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "read_file",
            "input": {"path": "a.py"},
        },
    ],
    "usage": {"input_tokens": 100, "output_tokens": 20},
}


def _transport(calls: list[dict]):
    """Транспорт-заглушка: запоминает запрос и отдаёт готовый ответ."""

    def send(url, api_key, payload, timeout):
        calls.append({"url": url, "key": api_key, "payload": payload})

        return REPLY

    return send


def test_complete_parses_text_and_tools() -> None:
    """Ответ разбирается на текст, вызовы и расход."""

    calls: list[dict] = []
    provider = AnthropicProvider(
        "https://api.example.org",
        "secret",
        "claude-sonnet-4",
        transport=_transport(calls),
    )

    reply = provider.complete([{"role": "user", "content": "привет"}])

    assert reply.text == "Готово."
    assert reply.calls[0].tool == "read_file"
    assert reply.calls[0].args == {"path": "a.py"}
    assert reply.usage["total_tokens"] == 120
    assert calls[0]["url"].endswith("/v1/messages")
    assert calls[0]["key"] == "secret"


def test_system_and_tool_messages_are_converted() -> None:
    """system выносится отдельно, tool-ответы склеиваются в user."""

    system, messages = to_anthropic_messages(
        [
            {"role": "system", "content": "ты агент"},
            {"role": "user", "content": "что в файле?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path": "a.py"}',
                        },
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "x = 1"},
        ]
    )

    assert system == "ты агент"
    assert messages[1]["content"][0]["type"] == "tool_use"
    assert messages[2]["content"][0]["type"] == "tool_result"


def test_tools_are_converted_to_input_schema() -> None:
    """Схемы инструментов переводятся в input_schema."""

    tools = to_anthropic_tools(
        [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "читает",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
    )

    assert tools[0]["name"] == "read_file"
    assert tools[0]["input_schema"]["type"] == "object"


def test_router_falls_back_on_error() -> None:
    """При сбое основного провайдера отвечает запасной."""

    class Broken:
        def complete(self, messages, tools=None, on_delta=None):
            raise ProviderError("основной недоступен")

    class Good:
        def complete(self, messages, tools=None, on_delta=None):
            return ProviderReply(text="ответ запасного")

    router = FallbackProvider(Broken(), Good())
    reply = router.complete([{"role": "user", "content": "привет"}])

    assert reply.text == "ответ запасного"
    assert router.used == "fallback"


def test_router_raises_without_secondary() -> None:
    """Без запасного провайдера ошибка уходит наружу."""

    class Broken:
        def complete(self, messages, tools=None, on_delta=None):
            raise ProviderError("нет связи")

    with pytest.raises(ProviderError):
        FallbackProvider(Broken()).complete([])


def test_cost_is_counted_per_million() -> None:
    """Стоимость считается по цене модели и расходу."""

    usage = {"prompt_tokens": 1_000_000, "completion_tokens": 0}

    assert estimate_cost("claude-sonnet-4", usage) == pytest.approx(3.0)
    assert price_for("local-model") == (0.0, 0.0)
    assert format_cost(0) == "$0"
    assert format_cost(0.0012) == "$0.0012"


def test_provider_chain_uses_fallback(monkeypatch) -> None:
    """Если задан запасной Anthropic, собирается резервная цепочка."""

    from terminal.core.agent import providers, settings

    monkeypatch.setattr(
        settings,
        "resolve_provider_values",
        lambda: {},
    )
    monkeypatch.setenv("AGENT_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("AGENT_API_KEY", "key")
    monkeypatch.setenv("AGENT_MODEL", "model")
    monkeypatch.setenv("AGENT_FALLBACK_BASE_URL", "https://api.example.org")
    monkeypatch.setenv("AGENT_FALLBACK_API_KEY", "fallback-key")
    monkeypatch.setenv("AGENT_FALLBACK_MODEL", "claude-sonnet-4")

    chain = providers.provider_chain()

    assert isinstance(chain, FallbackProvider)
    assert chain.secondary is not None


def test_provider_chain_without_fallback(monkeypatch) -> None:
    """Без запасного провайдера возвращается основной."""

    from terminal.core.agent import providers, settings

    monkeypatch.setattr(settings, "resolve_provider_values", lambda: {})
    monkeypatch.setenv("AGENT_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("AGENT_API_KEY", "key")
    monkeypatch.setenv("AGENT_MODEL", "model")
    monkeypatch.delenv("AGENT_FALLBACK_BASE_URL", raising=False)

    chain = providers.provider_chain()

    assert not isinstance(chain, FallbackProvider)
