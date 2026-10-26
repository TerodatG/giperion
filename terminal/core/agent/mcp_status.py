# Giperion/terminal/core/agent/mcp_status.py                           v001
# Статус MCP-серверов: инструменты, ресурсы и имена.
# Последнее изменение: вынесено из mcp, чтобы не раздувать клиент.

from terminal.core.agent.mcp_policy import McpServer


def probe(server: McpServer) -> dict:
    """Проверяет один сервер: инструменты, ресурсы и ошибку."""

    from terminal.core.agent import mcp

    result = {
        "name": server.name,
        "ok": False,
        "tools": 0,
        "resources": 0,
        "tool_names": [],
        "resource_names": [],
        "error": "",
    }

    try:
        client = mcp._session(server)
        tools = client.list_tools()
        resources = client.list_resources()
        result["tools"] = len(tools)
        result["resources"] = len(resources)
        result["tool_names"] = [
            str(item.get("name") or "")
            for item in tools
            if item.get("name")
        ]
        result["resource_names"] = [
            str(item.get("name") or item.get("uri") or "")
            for item in resources
        ]
        result["ok"] = True
    except mcp.McpError as error:
        mcp._drop_session(server.name)
        result["error"] = str(error)

    return result


def probe_all() -> list[dict]:
    """Проверяет все включённые серверы из конфига."""

    from terminal.core.agent import mcp

    return [
        probe(server)
        for server in mcp.load_servers()
        if server.enabled
    ]
