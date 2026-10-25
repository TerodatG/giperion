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


def _transport(message, usage=None):
    def call(url, key, payload, timeout):
        reply = {"choices": [{"message": message}]}

        if usage is not None:
            reply["usage"] = usage

        return reply

    return call


def test_native_brain_salvages_call_from_text() -> None:
    """Вызов, напечатанный текстом, не становится ответом."""

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=_transport(
            {"content": 'list_dir({"path": "tests"})'}
        ),
    )

    decision = NativeBrain(provider).decide("что в tests?")

    assert decision.action == "tools"
    assert decision.calls[0] == ToolCall(
        "list_dir",
        {"path": "tests"},
    )


def test_native_brain_keeps_plain_text_as_answer() -> None:
    """Похожий на код текст без вызова остаётся ответом."""

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=_transport(
            {"content": "Функция list_dir возвращает имена файлов."}
        ),
    )

    decision = NativeBrain(provider).decide("что делает list_dir?")

    assert decision.action == "answer"


def test_native_brain_counts_usage() -> None:
    """Расход токенов копится по ответам провайдера."""

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=_transport(
            {"content": "готово"},
            {"prompt_tokens": 120, "completion_tokens": 30},
        ),
    )

    brain = NativeBrain(provider)
    brain.decide("задача")
    brain.decide("ещё")

    assert brain.prompt_tokens == 240
    assert brain.completion_tokens == 60
    assert brain.total_tokens == 300
    assert brain.calls == 2


def test_native_brain_summarize_without_tools() -> None:
    """Итог запрашивается без схем инструментов."""

    seen = {}

    def transport(url, key, payload, timeout):
        seen["tools"] = payload.get("tools")
        return {"choices": [{"message": {"content": "итог"}}]}

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=transport,
    )

    text = NativeBrain(provider).summarize("подведи итог")

    assert text == "итог"
    assert seen["tools"] is None


def test_offline_message_names_lm_studio() -> None:
    """Для локального адреса подсказка про LM Studio."""

    from terminal.core.agent.providers import _offline_message

    text = _offline_message(
        "http://127.0.0.1:1234/v1/chat/completions",
        OSError("нет связи"),
    )

    assert "LM Studio" in text
    assert "Start Server" in text
    assert "Провайдер…" in text


def test_offline_message_for_remote_provider() -> None:
    """Для внешнего адреса остаётся общая формулировка."""

    from terminal.core.agent.providers import _offline_message

    text = _offline_message(
        "https://api.example.com/v1/chat/completions",
        OSError("нет связи"),
    )

    assert text.startswith("Провайдер недоступен")
    assert "LM Studio" not in text


def test_http_messages_explain_cause() -> None:
    """Коды ответа сопровождаются подсказкой, а не только цифрой."""

    from terminal.core.agent.providers import _http_message

    assert "ключ" in _http_message("http://x/v1", 401, "unauthorized")
    assert "ключ" in _http_message("http://x/v1", 403, "forbidden")
    assert "модель" in _http_message("http://x/v1", 404, "not found")
    assert "429" in _http_message("http://x/v1", 429, "slow down")
    assert _http_message("http://x/v1", 500, "boom") == (
        "Провайдер ответил 500: boom"
    )


def _ok_reply():
    return {"choices": [{"message": {"content": "ок"}}]}


def test_provider_retries_transient_error() -> None:
    """Временная ошибка повторяется с растущей паузой."""

    from terminal.core.agent.providers import ProviderRetry

    calls: list[int] = []
    waits: list[float] = []

    def transport(url, key, payload, timeout):
        calls.append(1)

        if len(calls) < 3:
            raise ProviderRetry("сеть моргнула")

        return _ok_reply()

    provider = OpenAICompatibleProvider(
        "http://x/v1",
        "secret",
        "test-model",
        transport=transport,
        retries=3,
        backoff=0.5,
        sleep=waits.append,
    )

    reply = provider.complete([{"role": "user", "content": "привет"}])

    assert reply.text == "ок"
    assert len(calls) == 3
    assert provider.retry_count == 2
    assert waits == [0.5, 1.0]


def test_provider_retries_rate_limit_with_server_hint() -> None:
    """Пауза из Retry-After важнее собственного backoff."""

    from terminal.core.agent.providers import ProviderRetry

    calls: list[int] = []
    waits: list[float] = []

    def transport(url, key, payload, timeout):
        calls.append(1)

        if len(calls) == 1:
            raise ProviderRetry("слишком часто", retry_after=2.5)

        return _ok_reply()

    provider = OpenAICompatibleProvider(
        "http://x/v1",
        "secret",
        "test-model",
        transport=transport,
        retries=3,
        backoff=0.5,
        sleep=waits.append,
    )

    provider.complete([{"role": "user", "content": "привет"}])

    assert waits == [2.5]


def test_provider_does_not_retry_permanent_error() -> None:
    """Ошибка ключа не повторяется: это не лечится ожиданием."""

    calls: list[int] = []

    def transport(url, key, payload, timeout):
        calls.append(1)

        raise ProviderError("Провайдер отклонил ключ")

    provider = OpenAICompatibleProvider(
        "http://x/v1",
        "secret",
        "test-model",
        transport=transport,
        retries=3,
        sleep=lambda seconds: None,
    )

    with pytest.raises(ProviderError):
        provider.complete([{"role": "user", "content": "привет"}])

    assert len(calls) == 1


def test_provider_gives_up_after_last_attempt() -> None:
    """После последней попытки ошибка уходит наружу."""

    from terminal.core.agent.providers import ProviderRetry

    calls: list[int] = []

    def transport(url, key, payload, timeout):
        calls.append(1)

        raise ProviderRetry("всё ещё нет связи")

    provider = OpenAICompatibleProvider(
        "http://x/v1",
        "secret",
        "test-model",
        transport=transport,
        retries=2,
        backoff=0.1,
        sleep=lambda seconds: None,
    )

    with pytest.raises(ProviderError):
        provider.complete([{"role": "user", "content": "привет"}])

    assert len(calls) == 2


def _http_error(value: str):
    import urllib.error
    from email.message import Message

    headers = Message()
    headers["Retry-After"] = value

    return urllib.error.HTTPError(
        "http://x/v1",
        429,
        "too many",
        headers,
        None,
    )


def test_retry_after_header_is_read() -> None:
    """Заголовок Retry-After разбирается и ограничивается разумным."""

    from terminal.core.agent.providers import _retry_after

    assert _retry_after(_http_error("3")) == 3.0
    assert _retry_after(_http_error("900")) == 60.0
    assert _retry_after(_http_error("скоро")) is None


def _stream_reply(text: str) -> dict:
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
    }


def test_streaming_gives_text_piece_by_piece() -> None:
    """Куски потока доходят до подписчика, ответ собирается целиком."""

    seen: list[str] = []

    def stream_transport(url, key, payload, timeout, on_delta):
        on_delta("При")
        on_delta("вет")
        return _stream_reply("Привет")

    provider = OpenAICompatibleProvider(
        "http://x/v1",
        "secret",
        "test-model",
        stream=True,
        stream_transport=stream_transport,
    )

    reply = provider.complete(
        [{"role": "user", "content": "привет"}],
        on_delta=seen.append,
    )

    assert seen == ["При", "вет"]
    assert reply.text == "Привет"
    assert reply.usage["completion_tokens"] == 2


def test_stream_falls_back_when_server_has_no_stream() -> None:
    """Если поток не поддержан, запрос повторяется обычным путём."""

    ordinary: list[int] = []

    def stream_transport(url, key, payload, timeout, on_delta):
        raise ProviderError("Адрес или модель не найдены")

    def transport(url, key, payload, timeout):
        ordinary.append(1)

        return _stream_reply("обычный ответ")

    provider = OpenAICompatibleProvider(
        "http://x/v1",
        "secret",
        "test-model",
        transport=transport,
        stream=True,
        stream_transport=stream_transport,
    )

    reply = provider.complete(
        [{"role": "user", "content": "привет"}],
        on_delta=lambda piece: None,
    )

    assert ordinary == [1]
    assert reply.text == "обычный ответ"


def test_stream_failure_after_start_is_not_repeated() -> None:
    """Обрыв посреди потока не дублирует уже показанный текст."""

    ordinary: list[int] = []

    def stream_transport(url, key, payload, timeout, on_delta):
        on_delta("начало")
        raise ProviderError("соединение закрыто")

    def transport(url, key, payload, timeout):
        ordinary.append(1)

        return _stream_reply("целиком")

    provider = OpenAICompatibleProvider(
        "http://x/v1",
        "secret",
        "test-model",
        transport=transport,
        stream=True,
        stream_transport=stream_transport,
    )

    with pytest.raises(ProviderError) as error:
        provider.complete(
            [{"role": "user", "content": "привет"}],
            on_delta=lambda piece: None,
        )

    assert "прервался" in str(error.value)
    assert ordinary == []


def test_native_brain_receives_stream_pieces() -> None:
    """Мозг отдаёт куски текста в подписчика и считает токены."""

    seen: list[str] = []

    def stream_transport(url, key, payload, timeout, on_delta):
        on_delta("гото")
        on_delta("во")
        return _stream_reply("готово")

    provider = OpenAICompatibleProvider(
        "http://x/v1",
        "secret",
        "test-model",
        stream=True,
        stream_transport=stream_transport,
    )

    brain = NativeBrain(provider)
    brain.on_delta = seen.append

    decision = brain.decide("задача")

    assert decision.action == "answer"
    assert decision.text == "готово"
    assert seen == ["гото", "во"]
    assert brain.total_tokens == 12


def test_tool_call_names_are_merged_from_deltas() -> None:
    """Имя инструмента собирается из частей потока без дублей."""

    from terminal.core.agent.providers import _merge_name

    assert _merge_name("", "read_file") == "read_file"
    assert _merge_name("read_file", "read_file") == "read_file"
    assert _merge_name("read_file", "file") == "read_file"
    assert _merge_name("read_", "file") == "read_file"
    assert _merge_name("read", "read_file") == "read_file"
