# Giperion/terminal/core/agent/provider_http.py                        v001
# HTTP-провайдер с tool calls и разбор ответов модели.
# Последнее изменение: вынесено из providers.

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from terminal.core.agent.protocol import ToolCall
from terminal.core.agent.registry import get_spec

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
    """Ответ модели: текст, вызовы, расход и исходное сообщение."""

    text: str = ""
    calls: tuple[ToolCall, ...] = ()
    usage: dict | None = None
    raw: dict | None = None


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


def _merge_name(current: str, piece: str) -> str:
    """Собирает имя инструмента из кусков потока."""

    if not piece:
        return current

    if not current:
        return piece

    if piece == current or current.endswith(piece):
        return current

    if piece.startswith(current):
        return piece

    return current + piece


def _stream_json(
    url: str,
    api_key: str,
    payload: dict,
    timeout: int,
    on_delta: Callable[[str], None],
) -> dict:
    """Читает SSE-поток и собирает из него обычный ответ провайдера."""

    body = dict(payload)
    body["stream"] = True
    body["stream_options"] = {"include_usage": True}

    data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
            "Accept": "text/event-stream",
        },
    )

    content: list[str] = []
    calls: dict[int, dict[str, str]] = {}
    usage: dict | None = None

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()

                if not line.startswith("data:"):
                    continue

                chunk = line[5:].strip()

                if chunk == "[DONE]":
                    break

                try:
                    event = json.loads(chunk)
                except json.JSONDecodeError:
                    continue

                if isinstance(event, dict):
                    found_usage = event.get("usage")

                    if isinstance(found_usage, dict):
                        usage = found_usage

                for choice in event.get("choices") or []:
                    delta = choice.get("delta") or {}
                    piece = delta.get("content")

                    if isinstance(piece, str) and piece:
                        content.append(piece)
                        on_delta(piece)

                    for item in delta.get("tool_calls") or []:
                        index = item.get("index")

                        if not isinstance(index, int):
                            index = len(calls)

                        slot = calls.setdefault(
                            index,
                            {"id": "", "name": "", "arguments": ""},
                        )

                        if item.get("id"):
                            slot["id"] = str(item["id"])

                        function = item.get("function") or {}

                        slot["name"] = _merge_name(
                            slot["name"],
                            function.get("name") or "",
                        )

                        arguments = function.get("arguments")

                        if isinstance(arguments, str):
                            slot["arguments"] += arguments
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]

        raise ProviderError(
            _http_message(url, error.code, detail)
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise ProviderError(_offline_message(url, error)) from error

    message: dict = {
        "role": "assistant",
        "content": "".join(content),
    }

    tool_calls = []

    for index in sorted(calls):
        slot = calls[index]

        if not slot["name"]:
            continue

        tool_calls.append(
            {
                "type": "function",
                "id": slot["id"] or f"call_{index}",
                "function": {
                    "name": slot["name"],
                    "arguments": slot["arguments"] or "{}",
                },
            }
        )

    if tool_calls:
        message["tool_calls"] = tool_calls

    reply: dict = {"choices": [{"message": message}]}

    if usage is not None:
        reply["usage"] = usage

    return reply


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
        stream: bool = False,
        stream_transport: Callable[..., dict] | None = None,
    ) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.api_key = str(api_key)
        self.model = str(model)
        self.timeout = timeout
        self.retries = max(1, int(retries))
        self.backoff = max(0.0, float(backoff))
        self.max_backoff = max(self.backoff, float(max_backoff))
        self.retry_count = 0
        self.stream = bool(stream)
        self._post = transport or _post_json
        self._stream = stream_transport or _stream_json
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
                    raise ProviderError(str(error)) from error

                delay = self._wait(attempt, error.retry_after)
                self.retry_count += 1
                attempt += 1
                self._sleep(delay)

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> ProviderReply:
        """Отправляет сообщения и возвращает текст и tool calls.

        Если включён поток и передан `on_delta`, текст приходит кусками по
        мере генерации. При сбое до первого куска запрос повторяется
        обычным способом; после — поток не дублируется, а ошибка уходит
        наружу.
        """

        if not self.base_url:
            raise ProviderError("Не задан base_url провайдера.")

        payload = {
            "model": self.model,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        data = None

        if self.stream and on_delta is not None:
            received = {"chars": 0}

            def delta(piece: str) -> None:
                received["chars"] += len(piece)
                on_delta(piece)

            try:
                data = self._stream(
                    self.base_url + "/chat/completions",
                    self.api_key,
                    payload,
                    self.timeout,
                    delta,
                )
            except ProviderError as error:
                if received["chars"]:
                    raise ProviderError(
                        "Поток ответа прервался после начала: "
                        f"{error}"
                    ) from error

                data = None

        if data is None:
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

        return ProviderReply(
            text=text,
            calls=tuple(calls),
            usage=usage,
            raw=dict(message, role="assistant"),
        )
