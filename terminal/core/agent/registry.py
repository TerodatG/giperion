# Giperion/terminal/core/agent/registry.py                            v003
# Совместимый фасад реестра; код в registry_specs/plugins/exec.
# Последнее изменение: разнесено по модулям.

from terminal.core.agent.protocol import ToolCall, ToolResult, ToolSpec
from terminal.core.agent.registry_exec import (
    approval_payload,
    execute,
    needs_approval,
    preview,
    validate_call,
)
from terminal.core.agent.registry_plugins import (
    plugin_tools,
    reload_plugins,
)
from terminal.core.agent.registry_specs import (
    TOOL_SPECS,
    all_specs,
    get_spec,
    tool_schemas,
    tools_prompt,
)

__all__ = [
    "TOOL_SPECS",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
    "all_specs",
    "approval_payload",
    "execute",
    "get_spec",
    "needs_approval",
    "plugin_tools",
    "preview",
    "reload_plugins",
    "tool_schemas",
    "tools_prompt",
    "validate_call",
]
