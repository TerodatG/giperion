# Giperion/terminal/core/agent/mcp_base.py                             v001
# Общие типы и разбор ответов MCP для stdio и HTTP-клиентов.
# Последнее изменение: вынесено из mcp.py, чтобы не было цикла импорта.

from terminal.core.agent.mcp_policy import McpServer, check_domains
from terminal.core.agent.protocol import ToolResult

PROTOCOL_VERSION = "2024-11-05"


class McpError(RuntimeError):
    """Ошибка MCP-сервера или протокола."""


class McpToolClient:
    """Разбор tools/resources поверх метода request."""

    def request(self, method: str, params: dict | None = None) -> dict:
        raise NotImplementedError

    def list_tools(self) -> list[dict]:
        """Список инструментов сервера."""

        result = self.request("tools/list", {})
        tools = result.get("tools")

        if not isinstance(tools, list):
            return []

        return [tool for tool in tools if isinstance(tool, dict)]

    def list_resources(self) -> list[dict]:
        """Список ресурсов сервера (если он их поддерживает)."""

        try:
            result = self.request("resources/list", {})
        except McpError:
            return []

        resources = result.get("resources")

        if not isinstance(resources, list):
            return []

        return [
            item for item in resources if isinstance(item, dict)
        ]

    def read_resource(self, uri: str) -> str:
        """Текст ресурса по URI."""

        result = self.request("resources/read", {"uri": str(uri)})
        contents = result.get("contents")

        if not isinstance(contents, list):
            return ""

        parts = []

        for item in contents:
            if not isinstance(item, dict):
                continue

            text = item.get("text")

            if isinstance(text, str) and text.strip():
                parts.append(text)

        return "\n".join(parts)

    def call_tool(self, name: str, arguments: dict) -> ToolResult:
        """Вызов инструмента и разбор content-блока."""

        server: McpServer = self.server  # type: ignore[attr-defined]
        error = check_domains(server, dict(arguments or {}))

        if error:
            return ToolResult(False, error)

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
