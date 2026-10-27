# Giperion/terminal/core/agent/registry_specs.py                      v001
# Схемы и справка по инструментам.
# Последнее изменение: каталог вынесен в registry_catalog.

from terminal.core.agent.protocol import ToolCall, ToolSpec
from terminal.core.agent.registry_catalog import TOOL_SPECS
from terminal.core.agent.registry_plugins import plugin_tools


def all_specs() -> tuple[ToolSpec, ...]:
    """Встроенные, плагинные и MCP-инструменты вместе."""

    from terminal.core.agent import mcp

    return TOOL_SPECS + plugin_tools()[0] + mcp.mcp_tools()[0]


def get_spec(name: str) -> ToolSpec | None:
    """Возвращает описание инструмента по имени."""

    return next(
        (spec for spec in all_specs() if spec.name == name),
        None,
    )


def tool_schemas() -> list[dict]:
    """Отдаёт схемы инструментов в формате function calling."""

    schemas = []

    for spec in all_specs():
        properties = {}

        for name, description in spec.args.items():
            kind = spec.types.get(name, "string")
            entry = {
                "type": kind,
                "description": description,
            }

            if kind == "array":
                entry["items"] = {"type": "string"}

            properties[name] = entry

        if spec.schema is not None:
            parameters = dict(spec.schema)
            parameters.setdefault("type", "object")
        else:
            parameters = {
                "type": "object",
                "properties": properties,
                "required": list(spec.required),
                "additionalProperties": False,
            }

        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": parameters,
                },
            }
        )

    return schemas


def tools_prompt() -> str:
    """Описывает инструменты так, как их увидит модель."""

    lines = []

    for spec in all_specs():
        args = "; ".join(
            f"{key}: {value}" for key, value in spec.args.items()
        )
        lines.append(
            f"- {spec.name}({args}) — {spec.description}"
        )

    return "\n".join(lines)


def _string_arg(call: ToolCall, name: str, default: str = "") -> str:
    """Достаёт строковый аргумент или поднимает ошибку."""

    if name not in call.args and default:
        return default

    value = call.args.get(name, default)

    if not isinstance(value, str):
        raise ValueError(f"Аргумент «{name}» должен быть строкой.")

    return value


def _int_arg(call: ToolCall, name: str, default: int = 0) -> int:
    """Целый аргумент: число или строка с числом."""

    value = call.args.get(name, default)

    if isinstance(value, bool):
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bool_arg(call: ToolCall, name: str, default: bool = False) -> bool:
    """Логический аргумент: bool или строка yes/true/1."""

    value = call.args.get(name, default)

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
            "да",
        )

    return default


def _list_arg(call: ToolCall, name: str) -> list[str]:
    """Список путей: массив или одна строка для совместимости."""

    value = call.args.get(name)

    if isinstance(value, list):
        return [str(item) for item in value]

    if isinstance(value, str) and value.strip():
        return [value]

    return []

