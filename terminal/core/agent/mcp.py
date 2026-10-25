# Giperion/terminal/core/agent/mcp.py                                  v001
# MCP-клиент: внешние инструменты по JSON-RPC через stdio.
# Последнее изменение: первый вариант — initialize, tools/list, tools/call.

import json
import os
import queue
import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path

from config import BASE_DIR, DATA_DIR
from terminal.core.agent import sandbox
from terminal.core.agent.protocol import ToolSpec, ToolResult
from shared.storage.json_store import read_json_object

CONFIG_FILE = DATA_DIR / "agent_mcp.json"
TIMEOUT = 20
PROTOCOL_VERSION = "2024-11-05"
NAME_RE = re.compile(r"[^a-z0-9_]+")
MAX_TOOLS = 60


class McpError(RuntimeError):
    """Ошибка MCP-сервера или протокола."""


@dataclass(frozen=True)
class McpServer:
    """Описание сервера из data/agent_mcp.json."""

    name: str
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


def _expand(value: str) -> str:
    """Подставляет ${VAR} из окружения, если переменная задана."""

    text = str(value or "")

    def replace(match: re.Match) -> str:
        return os.environ.get(match.group(1), "")

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, text)


def _safe_name(value: str) -> str:
    """Имя для инструмента: только латиница, цифры и подчёркивания."""

    text = NAME_RE.sub("_", str(value or "").strip().lower())
    text = re.sub(r"_+", "_", text).strip("_")

    return text[:40] or "server"


def load_servers(document: dict | None = None) -> list[McpServer]:
    """Читает конфиг серверов, пропуская битые записи."""

    data = document if document is not None else read_json_object(CONFIG_FILE)
    raw = data.get("servers")

    if not isinstance(raw, list):
        return []

    servers: list[McpServer] = []
    seen: set[str] = set()

    for item in raw:
        if not isinstance(item, dict):
            continue

        name = _safe_name(item.get("name") or "")

        if not name or name in seen:
            continue

        command = str(item.get("command") or "").strip()

        if not command:
            continue

        args = item.get("args")

        if not isinstance(args, list):
            args = []

        env = item.get("env")
        clean_env: dict[str, str] = {}

        if isinstance(env, dict):
            for key, value in env.items():
                if isinstance(key, str) and isinstance(value, str):
                    clean_env[key] = _expand(value)

        seen.add(name)
        servers.append(
            McpServer(
                name=name,
                command=command,
                args=tuple(str(arg) for arg in args),
                env=clean_env,
                enabled=item.get("enabled") is not False,
            )
        )

    return servers


class McpClient:
    """Один сеанс связи с сервером: запуск, JSON-RPC, закрытие."""

    def __init__(self, server: McpServer, timeout: int = TIMEOUT) -> None:
        self.server = server
        self.timeout = max(1, int(timeout))
        self.process: subprocess.Popen | None = None
        self._queue: queue.Queue = queue.Queue()
        self._next_id = 0
        self._lock = threading.Lock()

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

    def list_tools(self) -> list[dict]:
        """Список инструментов сервера."""

        result = self.request("tools/list", {})
        tools = result.get("tools")

        if not isinstance(tools, list):
            return []

        return [tool for tool in tools if isinstance(tool, dict)]

    def call_tool(self, name: str, arguments: dict) -> ToolResult:
        """Вызов инструмента и разбор content-блока."""

        result = self.request(
            "tools/call",
            {"name": name, "arguments": dict(arguments or {})},
        )

        parts = []
        content = result.get("content")

        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue

                if item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))

                elif item.get("type") == "resource":
                    resource = item.get("resource") or {}
                    parts.append(str(resource.get("text") or ""))

        text = "\n".join(part for part in parts if part).strip()
        failed = bool(result.get("isError"))

        return ToolResult(
            not failed,
            text or ("MCP: пустой ответ" if not failed else "MCP: ошибка"),
        )

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


def _mcp_enabled() -> bool:
    """Включены ли MCP-серверы в настройках."""

    try:
        from terminal.core.agent import settings

        return settings.mcp_enabled()
    except Exception:  # noqa: BLE001 — без настроек выключено
        return False


_cache: tuple[tuple[ToolSpec, ...], dict[str, tuple[str, str]]] | None = None
_lock = threading.Lock()


def reload_mcp() -> None:
    """Сбрасывает кеш инструментов MCP."""

    global _cache

    with _lock:
        _cache = None


def _build_cache() -> tuple[tuple[ToolSpec, ...], dict[str, tuple[str, str]]]:
    """Подключается к серверам и собирает их инструменты."""

    specs: list[ToolSpec] = []
    handlers: dict[str, tuple[str, str]] = {}

    for server in load_servers():
        if not server.enabled:
            continue

        try:
            with McpClient(server) as client:
                tools = client.list_tools()
        except McpError:
            continue

        for tool in tools:
            parsed = _spec_from_tool(server.name, tool)

            if parsed is None:
                continue

            spec, original = parsed

            if spec.name in handlers or len(specs) >= MAX_TOOLS:
                continue

            specs.append(spec)
            handlers[spec.name] = (server.name, original)

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
        with McpClient(server) as client:
            return client.call_tool(
                original,
                dict(arguments or {}),
            )
    except McpError as error:
        return ToolResult(False, str(error))
