# Giperion/terminal/core/agent/mcp.py                                  v001
# MCP-клиент: внешние инструменты по JSON-RPC через stdio.
# Последнее изменение: конфиг и allowlist вынесены в mcp_policy.py.

import atexit
import json
import queue
import subprocess
import threading
from pathlib import Path

from config import BASE_DIR, DATA_DIR
from terminal.core.agent import sandbox
from terminal.core.agent.mcp_base import (
    PROTOCOL_VERSION,
    McpError,
    McpToolClient,
)
from terminal.core.agent.mcp_policy import (
    McpServer,
    _safe_name,
    _tool_allowed,
    domain_allowed,  # noqa: F401 — реэкспорт для тестов
)
from terminal.core.agent.protocol import ToolResult, ToolSpec

CONFIG_FILE = DATA_DIR / "agent_mcp.json"
TIMEOUT = 20
MAX_TOOLS = 60


def load_servers(document: dict | None = None) -> list[McpServer]:
    """Читает конфиг по текущему пути CONFIG_FILE."""

    from terminal.core.agent import mcp_policy

    return mcp_policy.load_servers(document, CONFIG_FILE)


class McpClient(McpToolClient):
    """Один сеанс связи с сервером: запуск, JSON-RPC, закрытие."""

    def __init__(self, server: McpServer, timeout: int = TIMEOUT) -> None:
        self.server = server
        self.timeout = max(1, int(timeout))
        self.process: subprocess.Popen | None = None
        self._queue: queue.Queue = queue.Queue()
        self._next_id = 0
        self._lock = threading.Lock()
        self._request_lock = threading.Lock()

    def alive(self) -> bool:
        """Процесс сервера ещё жив."""

        return self.process is not None and self.process.poll() is None

    def __enter__(self) -> "McpClient":
        self.start()

        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def start(self) -> None:
        """Запускает сервер и выполняет initialize."""

        env = sandbox.plugin_env(BASE_DIR)

        for key, value in self.server.env.items():
            env[key] = value

        command = [self.server.command, *self.server.args]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(Path(BASE_DIR).resolve()),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except OSError as error:
            raise McpError(
                f"MCP-сервер «{self.server.name}» не запустился: {error}"
            ) from error

        threading.Thread(
            target=self._read_loop,
            daemon=True,
        ).start()

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

    def _read_loop(self) -> None:
        """Читает строки сервера и складывает их в очередь."""

        stream = self.process.stdout if self.process else None

        if stream is None:
            self._queue.put(None)

            return

        try:
            for line in stream:
                self._queue.put(line)
        except (OSError, ValueError):
            pass
        finally:
            self._queue.put(None)

    def send(self, message: dict) -> None:
        """Отправляет одно сообщение в stdin сервера."""

        if self.process is None or self.process.stdin is None:
            raise McpError("MCP-сервер не запущен.")

        try:
            self.process.stdin.write(
                json.dumps(message, ensure_ascii=False) + "\n"
            )
            self.process.stdin.flush()
        except (OSError, ValueError) as error:
            raise McpError(f"Не удалось отправить запрос: {error}") from error

    def notify(self, method: str, params: dict | None = None) -> None:
        """Уведомление без ответа."""

        message = {"jsonrpc": "2.0", "method": method}

        if params is not None:
            message["params"] = params

        self.send(message)

    def request(self, method: str, params: dict | None = None) -> dict:
        """Запрос с ожиданием ответа по id."""

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

            self.send(message)

            return self._receive(request_id)

    def _receive(self, request_id: int) -> dict:
        """Ждёт ответ именно на этот id."""

        while True:
            try:
                line = self._queue.get(timeout=self.timeout)
            except queue.Empty as error:
                raise McpError(
                    f"MCP-сервер «{self.server.name}» не ответил за "
                    f"{self.timeout} с."
                ) from error

            if line is None:
                raise McpError(
                    f"MCP-сервер «{self.server.name}» закрыл поток."
                )

            text = str(line).strip()

            if not text:
                continue

            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue

            if not isinstance(data, dict):
                continue

            if data.get("id") != request_id:
                continue

            error = data.get("error")

            if isinstance(error, dict):
                raise McpError(
                    f"{error.get('message') or 'ошибка MCP'} "
                    f"(код {error.get('code')})"
                )

            result = data.get("result")

            return result if isinstance(result, dict) else {}

    def close(self) -> None:
        """Останавливает сервер."""

        process = self.process
        self.process = None

        if process is None:
            return

        try:
            if process.stdin is not None:
                process.stdin.close()
        except OSError:
            pass

        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()

            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass


def _spec_from_tool(server: str, tool: dict) -> tuple[ToolSpec, str] | None:
    """Превращает MCP-инструмент в ToolSpec с именем mcp_<сервер>_<имя>."""

    raw_name = str(tool.get("name") or "").strip()

    if not raw_name:
        return None

    full_name = f"mcp_{_safe_name(server)}_{_safe_name(raw_name)}"
    full_name = full_name[:64]

    schema = tool.get("inputSchema")
    properties: dict[str, str] = {}
    required: list[str] = []

    if isinstance(schema, dict):
        raw_properties = schema.get("properties")

        if isinstance(raw_properties, dict):
            for key, value in raw_properties.items():
                if not isinstance(key, str):
                    continue

                description = ""

                if isinstance(value, dict):
                    description = str(value.get("description") or "")

                properties[key] = description or "аргумент MCP"

        raw_required = schema.get("required")

        if isinstance(raw_required, list):
            required = [
                str(item) for item in raw_required if isinstance(item, str)
            ]

    annotations = tool.get("annotations") or {}
    read_only = bool(
        isinstance(annotations, dict)
        and annotations.get("readOnlyHint") is True
    )

    description = str(tool.get("description") or "").strip()

    spec = ToolSpec(
        name=full_name,
        description=(
            f"MCP «{server}»: " + (description or raw_name)
        )[:400],
        args=properties,
        risk="read" if read_only else "write",
        required=tuple(required),
        permissions=(),
        schema=dict(schema) if isinstance(schema, dict) else None,
    )

    return spec, raw_name


def _spec_from_prompt(server: str, prompt: dict) -> tuple[ToolSpec, str] | None:
    """Превращает MCP-промпт в инструмент mcp_<сервер>_prompt_<имя>."""

    raw_name = str(prompt.get("name") or "").strip()

    if not raw_name:
        return None

    full_name = (
        f"mcp_{_safe_name(server)}_prompt_{_safe_name(raw_name)}"
    )[:64]
    properties: dict[str, str] = {}
    required: list[str] = []
    arguments = prompt.get("arguments")

    if isinstance(arguments, list):
        for item in arguments:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or "").strip()

            if not name:
                continue

            properties[name] = str(
                item.get("description") or "аргумент промпта"
            )

            if item.get("required") is True:
                required.append(name)

    description = str(prompt.get("description") or "").strip()
    spec = ToolSpec(
        name=full_name,
        description=(
            f"MCP-промпт «{server}»: " + (description or raw_name)
        )[:400],
        args=properties,
        risk="read",
        required=tuple(required),
    )

    return spec, raw_name


def _mcp_enabled() -> bool:
    """Включены ли MCP-серверы в настройках."""

    try:
        from terminal.core.agent import settings

        return settings.mcp_enabled()
    except Exception:  # noqa: BLE001 — без настроек выключено
        return False


_cache: tuple[tuple[ToolSpec, ...], dict[str, tuple[str, str]]] | None = None
_lock = threading.Lock()
_SESSIONS: dict[str, McpClient] = {}
_sessions_lock = threading.Lock()


def _session(server: McpServer) -> McpClient:
    """Живая сессия сервера: запускается один раз, а не на каждый вызов."""

    with _sessions_lock:
        client = _SESSIONS.get(server.name)

        if client is not None and client.alive():
            return client

        if client is not None:
            client.close()

        if server.transport in ("http", "sse"):
            from terminal.core.agent.mcp_http import McpHttpClient

            client = McpHttpClient(server)
        else:
            client = McpClient(server)

        client.start()
        _SESSIONS[server.name] = client

        return client


def _drop_session(name: str) -> None:
    """Закрывает сессию, чтобы следующий вызов запустил её заново."""

    with _sessions_lock:
        client = _SESSIONS.pop(name, None)

        if client is not None:
            client.close()


def close_sessions() -> None:
    """Закрывает все MCP-процессы."""

    with _sessions_lock:
        for client in _SESSIONS.values():
            client.close()

        _SESSIONS.clear()


atexit.register(close_sessions)


def reload_mcp() -> None:
    """Сбрасывает кеш инструментов MCP и закрывает сессии."""

    global _cache

    with _lock:
        _cache = None

    close_sessions()


def _build_cache() -> tuple[tuple[ToolSpec, ...], dict[str, tuple[str, str]]]:
    """Подключается к серверам и собирает их инструменты."""

    specs: list[ToolSpec] = []
    handlers: dict[str, tuple[str, str]] = {}

    for server in load_servers():
        if not server.enabled:
            continue

        try:
            tools = _session(server).list_tools()
        except McpError:
            _drop_session(server.name)
            continue

        for tool in tools:
            raw_name = tool.get("name")

            if not _tool_allowed(server, str(raw_name or "")):
                continue

            parsed = _spec_from_tool(server.name, tool)

            if parsed is None:
                continue

            spec, original = parsed

            if spec.name in handlers or len(specs) >= MAX_TOOLS:
                continue

            specs.append(spec)
            handlers[spec.name] = (server.name, original)

        try:
            prompts = _session(server).list_prompts()
        except McpError:
            prompts = []

        for prompt in prompts:
            raw_name = str(prompt.get("name") or "")

            if not _tool_allowed(server, raw_name):
                continue

            parsed = _spec_from_prompt(server.name, prompt)

            if parsed is None:
                continue

            spec, original = parsed

            if spec.name in handlers or len(specs) >= MAX_TOOLS:
                continue

            specs.append(spec)
            handlers[spec.name] = (
                server.name,
                "prompt:" + original,
            )

    return tuple(specs), handlers


def mcp_tools() -> tuple[tuple[ToolSpec, ...], dict[str, tuple[str, str]]]:
    """Инструменты MCP с кешем; пусто, если выключено."""

    global _cache

    if not _mcp_enabled():
        return (), {}

    with _lock:
        if _cache is None:
            _cache = _build_cache()

        return _cache


def call_tool(root: Path, name: str, arguments: dict | None = None) -> ToolResult:
    """Выполняет MCP-инструмент по имени."""

    _specs, handlers = mcp_tools()
    entry = handlers.get(name)

    if entry is None:
        return ToolResult(False, f"MCP-инструмент не найден: {name}")

    server_name, original = entry
    server = next(
        (
            item
            for item in load_servers()
            if item.name == server_name
        ),
        None,
    )

    if server is None:
        return ToolResult(False, f"MCP-сервер не найден: {server_name}")

    if not server.enabled:
        return ToolResult(False, f"MCP-сервер выключен: {server_name}")

    try:
        client = _session(server)
    except McpError as error:
        return ToolResult(False, str(error))

    try:
        if original.startswith("prompt:"):
            text = client.get_prompt(
                original[len("prompt:"):],
                dict(arguments or {}),
            )

            return ToolResult(
                True,
                text or "MCP: пустой промпт",
            )

        return client.call_tool(
            original,
            dict(arguments or {}),
        )
    except McpError as error:
        _drop_session(server_name)

        return ToolResult(False, str(error))



