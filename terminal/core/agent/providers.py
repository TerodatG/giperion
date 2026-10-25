# Giperion/terminal/core/agent/providers.py                          v001
# Провайдер с настоящими tool calls (OpenAI-совместимый) и мозг поверх него.
# Последнее изменение: первый вариант — chat/completions с function calling.

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from terminal.core.agent.protocol import AgentDecision, ToolCall
from terminal.core.agent.registry import get_spec, tool_schemas

TIMEOUT = 120

TEXT_CALL = re.compile(
    r"^([A-Za-z_]\w*)\s*\(\s*(\{.*\})\s*\)$",
    re.DOTALL,
)


def _salvage_call(text: str) -> ToolCall | None:
    """Достаёт вызов из текста, если провайдер не распарсил tool call.

    Некоторые локальные серверы иногда печатают вызов прямо в content.
    Если весь ответ — это «имя({...})» с известным инструментом, считаем
    это вызовом, а не ответом.
    """

    clean = str(text or "").strip().strip("`").strip()

    if len(clean) > 2000:
        return None

    match = TEXT_CALL.match(clean)

    if not match:
        return None

    name = match.group(1)

    if get_spec(name) is None:
        return None

    try:
        args = json.loads(match.group(2))
    except json.JSONDecodeError:
        return None

    if not isinstance(args, dict):
        return None

    return ToolCall(tool=name, args=args)


class ProviderError(RuntimeError):
    """Провайдер недоступен или ответил ошибкой."""


@dataclass(frozen=True)
class ProviderReply:
    """Ответ модели: текст и/или вызовы инструментов."""

    text: str = ""
    calls: tuple[ToolCall, ...] = ()
    usage: dict | None = None


def _post_json(
    url: str,
    api_key: str,
    payload: dict,
    timeout: int,
) -> dict:
    """Отправляет JSON и возвращает разобранный ответ."""

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]

        raise ProviderError(
            f"Провайдер ответил {error.code}: {detail}"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ProviderError(f"Провайдер недоступен: {error}") from error

    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProviderError("Провайдер вернул не JSON.") from error

    if not isinstance(value, dict):
        raise ProviderError("Провайдер вернул не объект.")

    return value


class OpenAICompatibleProvider:
    """Провайдер с /chat/completions и function calling."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = TIMEOUT,
        transport: Callable[..., dict] | None = None,
    ) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.api_key = str(api_key)
        self.model = str(model)
        self.timeout = timeout
        self._post = transport or _post_json

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ProviderReply:
        """Отправляет сообщения и возвращает текст и tool calls."""

        if not self.base_url:
            raise ProviderError("Не задан base_url провайдера.")

        payload = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        data = self._post(
            self.base_url + "/chat/completions",
            self.api_key,
            payload,
            self.timeout,
        )

        choices = data.get("choices")

        if not isinstance(choices, list) or not choices:
            raise ProviderError("В ответе нет choices.")

        message = choices[0].get("message") or {}

        text = message.get("content") or ""
        text = text if isinstance(text, str) else ""

        usage = data.get("usage")

        if not isinstance(usage, dict):
            usage = None

        calls = []

        for item in message.get("tool_calls") or []:
            function = item.get("function") or {}
            name = function.get("name")
            arguments = function.get("arguments") or "{}"

            if not isinstance(name, str) or not name:
                continue

            if isinstance(arguments, str):
                try:
                    args = json.loads(arguments)
                except json.JSONDecodeError as error:
                    raise ProviderError(
                        "Аргументы вызова — не JSON."
                    ) from error
            elif isinstance(arguments, dict):
                args = arguments
            else:
                args = {}

            if not isinstance(args, dict):
                args = {}

            calls.append(ToolCall(tool=name, args=args))

        return ProviderReply(text=text, calls=tuple(calls), usage=usage)


class NativeBrain:
    """Мозг агента поверх провайдера с tool calls."""

    native = True

    def __init__(self, provider: OpenAICompatibleProvider) -> None:
        self.provider = provider
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    @property
    def total_tokens(self) -> int:
        """Сколько токенов потрачено за всё время работы мозга."""

        return self.prompt_tokens + self.completion_tokens

    def decide(self, prompt: str) -> AgentDecision:
        """Возвращает решение с настоящими вызовами инструментов."""

        reply = self.provider.complete(
            [{"role": "user", "content": prompt}],
            tool_schemas(),
        )

        self.calls += 1

        usage = reply.usage if isinstance(reply.usage, dict) else {}

        for key, field in (
            ("prompt_tokens", "prompt_tokens"),
            ("completion_tokens", "completion_tokens"),
        ):
            value = usage.get(key)

            if isinstance(value, (int, float)):
                setattr(
                    self,
                    field,
                    getattr(self, field) + int(value),
                )

        if reply.calls:
            return AgentDecision(
                action="tools",
                calls=reply.calls,
            )

        salvaged = _salvage_call(reply.text)

        if salvaged is not None:
            return AgentDecision(
                action="tools",
                calls=(salvaged,),
            )

        if reply.text.strip():
            return AgentDecision(
                action="answer",
                text=reply.text.strip(),
            )

        raise ProviderError("Провайдер вернул пустой ответ.")

    def summarize(self, prompt: str) -> str:
        """Итог без инструментов: когда шаги кончились."""

        reply = self.provider.complete(
            [{"role": "user", "content": prompt}],
            None,
        )

        self.calls += 1

        usage = reply.usage if isinstance(reply.usage, dict) else {}

        for key, field in (
            ("prompt_tokens", "prompt_tokens"),
            ("completion_tokens", "completion_tokens"),
        ):
            value = usage.get(key)

            if isinstance(value, (int, float)):
                setattr(
                    self,
                    field,
                    getattr(self, field) + int(value),
                )

        return reply.text.strip()


def provider_from_env() -> OpenAICompatibleProvider | None:
    """Собирает провайдера из переменных окружения, если они заданы."""

    base_url = os.environ.get("AGENT_BASE_URL", "").strip()
    api_key = os.environ.get("AGENT_API_KEY", "").strip()
    model = os.environ.get("AGENT_MODEL", "").strip()

    if not (base_url and api_key and model):
        return None

    return OpenAICompatibleProvider(base_url, api_key, model)
