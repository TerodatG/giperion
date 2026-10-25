# Giperion/terminal/core/agent/providers.py                          v001
# Провайдер с настоящими tool calls (OpenAI-совместимый) и мозг поверх него.
# Последнее изменение: первый вариант — chat/completions с function calling.

import json
import os
import re
import time
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


class ProviderRetry(ProviderError):
    """Временная ошибка: запрос имеет смысл повторить."""

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


RETRYABLE_CODES = {408, 425, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class ProviderReply:
    """Ответ модели: текст и/или вызовы инструментов."""

    text: str = ""
    calls: tuple[ToolCall, ...] = ()
    usage: dict | None = None


def _is_local(url: str) -> bool:
    """Адрес ведёт на этот компьютер, а не в интернет."""

    host = url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]

    return host in ("127.0.0.1", "localhost", "::1", "0.0.0.0")


def _offline_message(url: str, error: Exception) -> str:
    """Понятное объяснение, если сервер не отвечает."""

    if _is_local(url):
        return (
            "Локальный сервер моделей не отвечает. Запусти LM Studio "
            "(или другой локальный сервер), нажми Start Server и проверь "
            f"адрес в окне «Провайдер…». Детали: {error}"
        )

    return f"Провайдер недоступен: {error}"


def _http_message(url: str, code: int, detail: str) -> str:
    """Подсказка к коду ответа: ключ, адрес или модель."""

    if code in (401, 403):
        hint = "Провайдер отклонил ключ — проверь его в «Провайдер…»."

        return f"{hint} Код {code}: {detail}"

    if code == 404:
        hint = (
            "Адрес или модель не найдены — проверь base URL и имя модели "
            "в «Провайдер…»."
        )

        return f"{hint} Код {code}: {detail}"

    if code == 429:
        return f"Провайдер ограничил частоту запросов. Код 429: {detail}"

    return f"Провайдер ответил {code}: {detail}"


def _retry_after(error: urllib.error.HTTPError) -> float | None:
    """Сколько секунд просит подождать сервер (заголовок Retry-After)."""

    try:
        value = error.headers.get("Retry-After")
    except (AttributeError, TypeError):
        return None

    if value is None:
        return None

    try:
        seconds = float(str(value).strip())
    except (TypeError, ValueError):
        return None

    if seconds < 0:
        return None

    return min(seconds, 60.0)


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
        message = _http_message(url, error.code, detail)

        if error.code in RETRYABLE_CODES:
            raise ProviderRetry(
                message,
                retry_after=_retry_after(error),
            ) from error

        raise ProviderError(message) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ProviderRetry(_offline_message(url, error)) from error

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
        retries: int = 3,
        backoff: float = 0.5,
        max_backoff: float = 8.0,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.api_key = str(api_key)
        self.model = str(model)
        self.timeout = timeout
        self.retries = max(1, int(retries))
        self.backoff = max(0.0, float(backoff))
        self.max_backoff = max(self.backoff, float(max_backoff))
        self.retry_count = 0
        self._post = transport or _post_json
        self._sleep = sleep or time.sleep

    def _wait(self, attempt: int, retry_after: float | None) -> float:
        """Пауза перед повтором: просьба сервера или рост с множителем."""

        if retry_after is not None:
            return min(retry_after, self.max_backoff)

        return min(self.backoff * (2 ** (attempt - 1)), self.max_backoff)

    def _send(self, payload: dict) -> dict:
        """Отправляет запрос, повторяя временные ошибки."""

        url = self.base_url + "/chat/completions"
        attempt = 1

        while True:
            try:
                return self._post(
                    url,
                    self.api_key,
                    payload,
                    self.timeout,
                )
            except ProviderRetry as error:
                if attempt >= self.retries:
                    raise

                delay = self._wait(attempt, error.retry_after)
                self.retry_count += 1
                attempt += 1
                self._sleep(delay)

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

        data = self._send(payload)

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

    def __init__(
        self,
        provider: OpenAICompatibleProvider,
        limits=None,
    ) -> None:
        from terminal.core.agent.budget import BudgetLimits

        self.provider = provider
        self.limits = limits if limits is not None else BudgetLimits()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.cost = 0.0

    @property
    def total_tokens(self) -> int:
        """Сколько токенов потрачено за всё время работы мозга."""

        return self.prompt_tokens + self.completion_tokens

    def _account(self, reply: ProviderReply) -> None:
        """Копит токены и стоимость по ответу провайдера."""

        from terminal.core.agent.budget import cost_of

        self.calls += 1

        usage = reply.usage if isinstance(reply.usage, dict) else {}

        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")

        prompt = int(prompt) if isinstance(prompt, int) else 0
        completion = int(completion) if isinstance(completion, int) else 0

        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.cost += cost_of(prompt, completion, self.limits)

    def decide(self, prompt: str) -> AgentDecision:
        """Возвращает решение с настоящими вызовами инструментов."""

        reply = self.provider.complete(
            [{"role": "user", "content": prompt}],
            tool_schemas(),
        )

        self._account(reply)

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

        self._account(reply)

        return reply.text.strip()


def provider_from_env() -> OpenAICompatibleProvider | None:
    """Собирает провайдера из переменных окружения, если они заданы."""

    base_url = os.environ.get("AGENT_BASE_URL", "").strip()
    api_key = os.environ.get("AGENT_API_KEY", "").strip()
    model = os.environ.get("AGENT_MODEL", "").strip()

    if not (base_url and api_key and model):
        return None

    return OpenAICompatibleProvider(base_url, api_key, model)
