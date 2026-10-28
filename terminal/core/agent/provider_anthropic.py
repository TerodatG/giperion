# Giperion/terminal/core/agent/provider_anthropic.py                   v001
# Провайдер Anthropic Messages API: текст и tool_use.

import json
import urllib.error
import urllib.request

from terminal.core.agent.protocol import ToolCall
from terminal.core.agent.provider_http import (
    ProviderError,
    ProviderReply,
    _is_local,
    _offline_message,
)

DEFAULT_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096
TIMEOUT = 120


def _post_json(
    url: str,
    api_key: str,
    payload: dict,
    timeout: int,
    version: str = DEFAULT_VERSION,
) -> dict:
    """Отправляет запрос в Messages API."""

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": version,
            "user-agent": "Giperion/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        text = error.read().decode("utf-8", errors="replace")[:300]

        raise ProviderError(
            f"Anthropic ответил {error.code}: {text}"
        ) from error
    except (urllib.error.URLError, OSError) as error:
        raise ProviderError(
            _offline_message(url, error) if _is_local(url)
            else f"Anthropic недоступен: {error}"
        ) from error
    except ValueError as error:
        raise ProviderError("Anthropic вернул не JSON") from error


def to_anthropic_tools(tools: list[dict] | None) -> list[dict]:
    """Переводит OpenAI-схемы инструментов в формат Anthropic."""

    converted = []

    for item in tools or []:
        function = item.get("function") if isinstance(item, dict) else None

        if not isinstance(function, dict):
            continue

        converted.append(
            {
                "name": function.get("name", ""),
                "description": function.get("description", ""),
                "input_schema": function.get("parameters") or {
                    "type": "object",
                    "properties": {},
                },
            }
        )

    return converted


def to_anthropic_messages(
    messages: list[dict],
) -> tuple[str, list[dict]]:
    """Делит сообщения на system и обычные, склеивая tool-ответы."""

    system_parts = []
    converted: list[dict] = []

    for message in messages:
        role = str(message.get("role") or "user")
        content = message.get("content")

        if role == "system":
            system_parts.append(str(content or ""))
            continue

        if role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": str(message.get("tool_call_id") or ""),
                "content": str(content or ""),
            }

            if converted and converted[-1]["role"] == "user":
                converted[-1]["content"].append(block)
            else:
                converted.append({"role": "user", "content": [block]})

            continue

        blocks = []

        if content:
            blocks.append({"type": "text", "text": str(content)})

        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            blocks.append(
                {
                    "type": "tool_use",
                    "id": str(call.get("id") or ""),
                    "name": str(function.get("name") or ""),
                    "input": _loads(function.get("arguments")),
                }
            )

        converted.append({"role": role, "content": blocks or [{"type": "text", "text": ""}]})

    return "\n\n".join(part for part in system_parts if part), converted


def _loads(raw) -> dict:
    """Аргументы инструмента приходят строкой JSON."""

    if isinstance(raw, dict):
        return raw

    try:
        value = json.loads(str(raw or "{}"))
    except ValueError:
        return {}

    return value if isinstance(value, dict) else {}


class AnthropicProvider:
    """Провайдер с /v1/messages."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = TIMEOUT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        transport=None,
        version: str = DEFAULT_VERSION,
    ) -> None:
        self.base_url = str(base_url or "").rstrip("/")
        self.api_key = str(api_key or "")
        self.model = str(model or "")
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.version = version
        self._post = transport or _post_json

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        on_delta=None,
    ) -> ProviderReply:
        """Отправляет сообщения и разбирает ответ."""

        if not self.base_url:
            raise ProviderError("Не задан base_url провайдера.")

        system, converted = to_anthropic_messages(messages)
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": converted,
        }

        if system:
            payload["system"] = system

        anthropic_tools = to_anthropic_tools(tools)

        if anthropic_tools:
            payload["tools"] = anthropic_tools

        data = self._post(
            self.base_url + "/v1/messages",
            self.api_key,
            payload,
            self.timeout,
        )

        return self._reply(data)

    def _reply(self, data: dict) -> ProviderReply:
        """Собирает текст, вызовы и расход из ответа."""

        texts = []
        calls = []

        for block in data.get("content") or []:
            if not isinstance(block, dict):
                continue

            if block.get("type") == "text":
                texts.append(str(block.get("text") or ""))
            elif block.get("type") == "tool_use":
                calls.append(
                    ToolCall(
                        tool=str(block.get("name") or ""),
                        args=block.get("input") or {},
                    )
                )

        usage = data.get("usage") or {}
        prompt = int(usage.get("input_tokens") or 0)
        completion = int(usage.get("output_tokens") or 0)

        return ProviderReply(
            text="".join(texts).strip(),
            calls=tuple(calls),
            usage={
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            },
            raw=data,
        )
