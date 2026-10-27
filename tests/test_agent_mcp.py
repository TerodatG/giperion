# Giperion/tests/test_agent_mcp.py                                    v001
# MCP-клиент: конфиг, рукопожатие, список инструментов и вызовы.

import json
import sys

import pytest

from terminal.core.agent import mcp, registry, settings
from terminal.core.agent.protocol import ToolCall

STUB = '''
import json
import sys


def send(message):
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\\n")
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()

    if not line:
        continue

    message = json.loads(line)
    method = message.get("method")
    request_id = message.get("id")

    if method == "initialize":
        send({"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "stub", "version": "1"},
        }})
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": request_id, "result": {"tools": [
            {
                "name": "echo",
                "description": "Вернуть текст",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string", "description": "текст"}},
                    "required": ["text"],
                },
                "annotations": {"readOnlyHint": True},
            },
            {
                "name": "write_note",
                "description": "Записать заметку",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        ]}})
    elif method == "resources/list":
        send({"jsonrpc": "2.0", "id": request_id, "result": {
            "resources": [
                {
                    "uri": "mem://note",
                    "name": "note",
                    "mimeType": "text/plain",
                }
            ]
        }})
    elif method == "resources/read":
        params = message.get("params") or {}
        uri = str(params.get("uri") or "")
        send({"jsonrpc": "2.0", "id": request_id, "result": {
            "contents": [
                {"uri": uri, "text": "ресурс: " + uri},
            ]
        }})
    elif method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name == "write_note":
            send({"jsonrpc": "2.0", "id": request_id, "result": {
                "isError": True,
                "content": [{"type": "text", "text": "нельзя"}],
            }})
        else:
            send({"jsonrpc": "2.0", "id": request_id, "result": {
                "content": [{"type": "text", "text": "эхо: " + str(arguments.get("text", ""))}],
            }})
    else:
        send({"jsonrpc": "2.0", "id": request_id, "error": {
            "code": -32601,
            "message": "нет метода",
        }})
'''

SILENT = '''
import sys

for _line in sys.stdin:
    pass
'''


def _server_file(tmp_path, code: str = STUB):
    path = tmp_path / "server.py"
    path.write_text(code, encoding="utf-8")

    return path


def _config(tmp_path, server_path, name="stub", enabled=True) -> dict:
    return {
        "servers": [
            {
                "name": name,
                "command": sys.executable,
                "args": [str(server_path)],
                "enabled": enabled,
            }
        ]
    }


@pytest.fixture()
def mcp_config(tmp_path, monkeypatch):
    server_path = _server_file(tmp_path)
    document = _config(tmp_path, server_path)

    monkeypatch.setattr(
        mcp,
        "CONFIG_FILE",
        tmp_path / "agent_mcp.json",
    )
    (tmp_path / "agent_mcp.json").write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "mcp_enabled", lambda: True)
    mcp.reload_mcp()

    yield tmp_path / "agent_mcp.json"

    mcp.reload_mcp()


def test_load_servers_skips_broken() -> None:
    """Битые и повторные записи конфига пропускаются."""

    servers = mcp.load_servers(
        {
            "servers": [
                {"name": "Good Server", "command": "python"},
                {"name": "good_server", "command": "python"},
                {"name": "no-command"},
                "мусор",
                {"name": "with env", "command": "python", "env": {"X": "1"}},
            ]
        }
    )

    assert [item.name for item in servers] == ["good_server", "with_env"]
    assert servers[0].args == ()
    assert servers[1].env == {"X": "1"}


def test_env_expansion(monkeypatch) -> None:
    """${VAR} в env подставляется из окружения."""

    monkeypatch.setenv("MCP_TEST_VALUE", "секрет")

    servers = mcp.load_servers(
        {
            "servers": [
                {
                    "name": "s",
                    "command": "python",
                    "env": {"TOKEN": "prefix-${MCP_TEST_VALUE}"},
                }
            ]
        }
    )

    assert servers[0].env["TOKEN"] == "prefix-секрет"


def test_client_handshake_and_calls(tmp_path) -> None:
    """Клиент проходит initialize, читает tools и вызывает инструмент."""

    server = mcp.McpServer(
        name="stub",
        command=sys.executable,
        args=(str(_server_file(tmp_path)),),
    )

    with mcp.McpClient(server, timeout=10) as client:
        tools = client.list_tools()

        assert [tool["name"] for tool in tools] == ["echo", "write_note"]

        result = client.call_tool("echo", {"text": "привет"})

        assert result.ok
        assert result.text == "эхо: привет"

        failed = client.call_tool("write_note", {"path": "a.txt"})

        assert not failed.ok
        assert failed.text == "нельзя"


def test_client_timeout(tmp_path) -> None:
    """Молчащий сервер даёт понятную ошибку по таймауту."""

    server = mcp.McpServer(
        name="silent",
        command=sys.executable,
        args=(str(_server_file(tmp_path, SILENT)),),
    )

    with pytest.raises(mcp.McpError) as error:
        with mcp.McpClient(server, timeout=1):
            pass

    assert "не ответил" in str(error.value)


def test_registry_exposes_mcp_tools(mcp_config) -> None:
    """MCP-инструменты попадают в реестр и выполняются."""

    specs = {spec.name: spec for spec in registry.all_specs()}

    assert "mcp_stub_echo" in specs
    assert "mcp_stub_write_note" in specs

    echo = specs["mcp_stub_echo"]
    note = specs["mcp_stub_write_note"]

    assert echo.risk == "read"
    assert note.risk == "write"
    assert echo.schema is not None

    schema = next(
        item
        for item in registry.tool_schemas()
        if item["function"]["name"] == "mcp_stub_echo"
    )

    assert schema["function"]["parameters"]["required"] == ["text"]

    result = registry.execute(
        mcp_config.parent,
        ToolCall("mcp_stub_echo", {"text": "раз"}),
    )

    assert result.ok
    assert result.text == "эхо: раз"

    assert registry.needs_approval(
        ToolCall("mcp_stub_write_note", {"path": "a.txt"})
    )


def test_mcp_disabled_by_default(tmp_path, monkeypatch) -> None:
    """Без галочки серверы не опрашиваются."""

    server_path = _server_file(tmp_path)

    monkeypatch.setattr(
        mcp,
        "CONFIG_FILE",
        tmp_path / "agent_mcp.json",
    )
    (tmp_path / "agent_mcp.json").write_text(
        json.dumps(_config(tmp_path, server_path), ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "mcp_enabled", lambda: False)
    mcp.reload_mcp()

    assert mcp.mcp_tools() == ((), {})

    mcp.reload_mcp()


def test_validate_uses_schema_required(mcp_config) -> None:
    """Для MCP проверяется только наличие обязательных аргументов."""

    assert registry.validate_call(
        ToolCall("mcp_stub_echo", {"text": "x"})
    ) is None

    missing = registry.validate_call(
        ToolCall("mcp_stub_echo", {})
    )

    assert missing is not None
    assert "text" in missing.text

    # Число вместо строки отдаём серверу: его схема сама решит.
    assert registry.validate_call(
        ToolCall("mcp_stub_echo", {"text": 5})
    ) is None

def test_allowlist_is_parsed() -> None:
    """Списки tools и domains читаются и нормализуются."""

    servers = mcp.load_servers(
        {
            "servers": [
                {
                    "name": "web",
                    "command": "python",
                    "tools": ["Fetch", "fetch", "other"],
                    "domains": ["Example.com", "*.wikipedia.org"],
                }
            ]
        }
    )

    assert servers[0].tools == ("fetch", "other")
    assert servers[0].domains == ("example.com", "*.wikipedia.org")


def test_tool_allowlist_filters() -> None:
    """Пустой список разрешает всё, иначе — только перечисленное."""

    restricted = mcp.McpServer("web", "python", tools=("fetch",))

    assert mcp._tool_allowed(restricted, "fetch")
    assert not mcp._tool_allowed(restricted, "write")

    open_server = mcp.McpServer("web", "python")

    assert mcp._tool_allowed(open_server, "anything")


def test_domain_allowlist() -> None:
    """Точный домен и поддомены через *. работают."""

    assert mcp.domain_allowed("example.com", ("example.com",))
    assert mcp.domain_allowed(
        "ru.wikipedia.org",
        ("*.wikipedia.org",),
    )
    assert not mcp.domain_allowed(
        "wikipedia.org",
        ("*.wikipedia.org",),
    )
    assert mcp.domain_allowed("любой.рф", ())


def test_client_blocks_forbidden_domain() -> None:
    """Запрещённый домен не доходит до сервера."""

    server = mcp.McpServer(
        "web",
        "python",
        domains=("example.com",),
    )
    client = mcp.McpClient(server)
    result = client.call_tool("fetch", {"url": "https://python.org"})

    assert not result.ok
    assert "не разрешён" in result.text

    allowed = pytest.raises(mcp.McpError)

    with allowed:
        client.call_tool(
            "fetch",
            {"url": "https://example.com/page"},
        )

def test_session_is_reused(monkeypatch) -> None:
    """Сессия сервера переиспользуется, пока процесс жив."""

    from terminal.core.agent import mcp

    created: list = []

    class FakeClient:
        def __init__(self, server):
            self.server = server
            self.started = False
            self.closed = False
            created.append(self)

        def start(self):
            self.started = True

        def alive(self):
            return self.started and not self.closed

        def close(self):
            self.closed = True

    monkeypatch.setattr(mcp, "McpClient", FakeClient)
    mcp.close_sessions()

    server = mcp.McpServer("test", "python")
    first = mcp._session(server)
    second = mcp._session(server)

    assert first is second
    assert len(created) == 1

    first.closed = True
    third = mcp._session(server)

    assert third is not first
    assert len(created) == 2

    mcp.close_sessions()

    assert third.closed
    assert mcp._SESSIONS == {}

def test_resources_and_probe(tmp_path) -> None:
    """Клиент читает ресурсы, probe показывает статус."""

    from terminal.core.agent import mcp, mcp_status

    server = mcp.McpServer(
        "stub",
        sys.executable,
        (str(_server_file(tmp_path)),),
    )

    with mcp.McpClient(server) as client:
        resources = client.list_resources()

        assert resources[0]["uri"] == "mem://note"
        assert "ресурс: mem://note" in client.read_resource("mem://note")

    status = mcp_status.probe(server)

    assert status["ok"]
    assert status["tools"] >= 2
    assert status["resources"] == 1

    mcp.close_sessions()


def test_http_transport_with_token(monkeypatch) -> None:
    """HTTP MCP выполняет initialize, tools и call с Bearer-токеном."""

    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from terminal.core.agent.mcp_http import McpHttpClient

    seen: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            message = json.loads(self.rfile.read(length) or b"{}")
            seen["auth"] = str(self.headers.get("Authorization") or "")
            method = str(message.get("method") or "")
            request_id = message.get("id")

            if method == "notifications/initialized":
                self.send_response(202)
                self.end_headers()

                return

            if method == "tools/call":
                text = message["params"]["arguments"]["text"]
                result = {
                    "content": [{"type": "text", "text": "эхо: " + text}]
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Эхо",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"text": {"type": "string"}},
                                "required": ["text"],
                            },
                            "annotations": {"readOnlyHint": True},
                        }
                    ]
                }
            else:
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "http-stub", "version": "1"},
                }

            body = json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "result": result},
                ensure_ascii=False,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("MCP_TEST_TOKEN", "secret-token")

    try:
        config = mcp.McpServer(
            "remote",
            transport="http",
            url=f"http://127.0.0.1:{server.server_port}/mcp",
            token_env="MCP_TEST_TOKEN",
        )
        client = McpHttpClient(config)
        client.start()

        tools = client.list_tools()
        result = client.call_tool("echo", {"text": "привет"})

        assert [tool["name"] for tool in tools] == ["echo"]
        assert result.ok
        assert result.text == "эхо: привет"
        assert seen["auth"] == "Bearer secret-token"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_http_config_requires_url() -> None:
    """Для http-транспорта нужен url, для stdio — command."""

    servers = mcp.load_servers(
        {
            "servers": [
                {"name": "remote", "transport": "http"},
                {"name": "empty"},
                {
                    "name": "ok",
                    "transport": "http",
                    "url": "https://example.com/mcp",
                },
            ]
        }
    )

    assert [server.name for server in servers] == ["ok"]
    assert servers[0].transport == "http"


def test_sse_parser_takes_last_event() -> None:
    """SSE-ответ разбирается по data-строкам."""

    from terminal.core.agent.mcp_http import _parse

    raw = (
        b'data: {"jsonrpc":"2.0","id":1,"result":{"a":1}}\n\n'
        b'data: {"jsonrpc":"2.0","id":1,"result":{"a":2}}\n\n'
    )

    assert _parse(raw, "text/event-stream")["result"] == {"a": 2}


def test_prompts_and_prompt_tool_spec() -> None:
    """Промпты читаются и превращаются в read-only инструмент."""

    from terminal.core.agent.mcp_base import McpToolClient

    class Client(McpToolClient):
        server = mcp.McpServer("stub", "python")

        def request(self, method, params=None):
            if method == "prompts/list":
                return {
                    "prompts": [
                        {
                            "name": "review",
                            "description": "Проверить код",
                            "arguments": [
                                {
                                    "name": "path",
                                    "description": "файл",
                                    "required": True,
                                }
                            ],
                        }
                    ]
                }

            if method == "prompts/get":
                return {
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": "проверь " + params["arguments"]["path"],
                            },
                        }
                    ]
                }

            return {}

    client = Client()

    assert client.list_prompts()[0]["name"] == "review"
    assert client.get_prompt("review", {"path": "a.py"}) == "проверь a.py"

    parsed = mcp._spec_from_prompt("stub", client.list_prompts()[0])

    assert parsed is not None
    spec, name = parsed

    assert name == "review"
    assert spec.name == "mcp_stub_prompt_review"
    assert spec.risk == "read"
    assert spec.required == ("path",)
