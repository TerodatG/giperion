# Giperion/terminal/core/agent/mcp_http.py                            v001
# MCP поверх HTTP/SSE: JSON-RPC POST, Bearer-токен из env.
# Последнее изменение: первый вариант — initialize, tools, ресурсы.

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from terminal.core.agent.mcp_base import (
    PROTOCOL_VERSION,
    McpError,
    McpToolClient,
)
from terminal.core.agent.mcp_policy import McpServer

MAX_RESPONSE = 1_000_000
LOOPBACK = {"127.0.0.1", "localhost", "::1"}


def _endpoint(url: str) -> str:
    """Проверяет адрес MCP: http/https, без приватных сетей."""

    from terminal.core.agent import web

    target = str(url or "").strip()

    try:
        parts = urllib.parse.urlsplit(target)
    except ValueError as error:
        raise McpError(f"Некорректный URL MCP: {error}") from error

    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise McpError("MCP URL должен быть http/https.")

    host = parts.hostname.lower()

    if host in LOOPBACK:
        return target

    if not web.is_public_host(host):
        raise McpError("MCP URL ведёт в локальную или приватную сеть.")

    if not web.egress_allowed(host):
        raise McpError(f"Домен «{host}» не входит в общий allowlist.")

    return target


def _parse(raw: bytes, content_type: str) -> dict:
    """Разбирает JSON или последнее data-событие SSE."""

    text = raw.decode("utf-8", errors="replace").strip()

    if not text:
        raise McpError("MCP вернул пустой ответ.")

    if "text/event-stream" in content_type or text.startswith("data:"):
        found: dict | None = None

        for line in text.splitlines():
            if not line.startswith("data:"):
                continue

            payload = line[5:].strip()

            try:
                value = json.loads(payload)
            except json.JSONDecodeError:
                continue

            if isinstance(value, dict):
                found = value

        if found is None:
            raise McpError("MCP SSE без JSON-события.")

        return found

    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise McpError(f"MCP вернул не JSON: {error}") from error

    if not isinstance(value, dict):
        raise McpError("MCP вернул не объект.")

    return value


class McpHttpClient(McpToolClient):
    """Клиент удалённого MCP-сервера по HTTP/SSE."""

    def __init__(self, server: McpServer, timeout: int = 20) -> None:
        self.server = server
        self.timeout = max(1, int(timeout))
        self._next_id = 0
        self._lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._alive = False
        self._token = ""
        self._token_until = 0.0

    def alive(self) -> bool:
        return self._alive

    def start(self) -> None:
        """Проверяет URL и выполняет initialize."""

        _endpoint(self.server.url)
        self._alive = True

        try:
            self.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "giperion-terminal",
                        "version": "1.0",
                    },
                },
            )
            self.notify("notifications/initialized")
        except McpError:
            self._alive = False
            raise

    def _oauth_token(self) -> str:
        """Токен из env или OAuth client credentials."""

        name = self.server.token_env.strip()

        if name:
            value = os.environ.get(name, "").strip()

            if not value:
                raise McpError(
                    f"Не задан токен MCP: переменная {name}."
                )

            return value

        if not self.server.token_url:
            return ""

        if self._token and time.monotonic() < self._token_until:
            return self._token

        client_id = os.environ.get(
            self.server.client_id_env,
            "",
        ).strip()
        secret = os.environ.get(
            self.server.client_secret_env,
            "",
        ).strip()

        if not client_id or not secret:
            raise McpError(
                "OAuth MCP: не заданы client_id/client_secret."
            )

        _endpoint(self.server.token_url)
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": secret,
                "scope": self.server.scope,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.server.token_url,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                payload = json.loads(
                    response.read(MAX_RESPONSE).decode(
                        "utf-8",
                        errors="replace",
                    )
                )
        except (OSError, json.JSONDecodeError) as error:
            raise McpError(f"OAuth MCP не выдал токен: {error}") from error

        token = str(payload.get("access_token") or "").strip()

        if not token:
            raise McpError("OAuth MCP: пустой access_token.")

        try:
            expires = int(payload.get("expires_in") or 300)
        except (TypeError, ValueError):
            expires = 300

        self._token = token
        self._token_until = time.monotonic() + max(30, expires - 30)

        return token

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        token = self._oauth_token()

        if token:
            headers["Authorization"] = "Bearer " + token

        return headers

    def _post(self, message: dict, allow_empty: bool = False) -> dict:
        data = json.dumps(message, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.server.url,
            data=data,
            headers=self._headers(),
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                raw = response.read(MAX_RESPONSE + 1)
                content_type = str(
                    response.headers.get("Content-Type") or ""
                )
        except urllib.error.HTTPError as error:
            body = error.read(2_000).decode("utf-8", errors="replace")
            raise McpError(
                f"MCP HTTP {error.code}: {body.strip()[:300]}"
            ) from error
        except OSError as error:
            raise McpError(f"MCP недоступен: {error}") from error

        if len(raw) > MAX_RESPONSE:
            raise McpError(
                f"MCP ответ больше {MAX_RESPONSE // 1000} КБ."
            )

        if allow_empty and not raw.strip():
            return {}

        return _parse(raw, content_type)

    def notify(self, method: str, params: dict | None = None) -> None:
        message = {"jsonrpc": "2.0", "method": method}

        if params is not None:
            message["params"] = params

        self._post(message, allow_empty=True)

    def request(self, method: str, params: dict | None = None) -> dict:
        with self._request_lock:
            with self._lock:
                self._next_id += 1
                request_id = self._next_id

            message = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
            }

            if params is not None:
                message["params"] = params

            data = self._post(message)
            error = data.get("error")

            if isinstance(error, dict):
                raise McpError(
                    f"{error.get('message') or 'ошибка MCP'} "
                    f"(код {error.get('code')})"
                )

            result = data.get("result")

            return result if isinstance(result, dict) else {}

    def close(self) -> None:
        self._alive = False
