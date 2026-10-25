# Giperion/terminal/core/agent/registry.py                          v002
# Реестр инструментов агента, их схемы, риски и плагины.
# Последнее изменение: плагины из data/agent_tools по явному разрешению.

import importlib.util
import json
import re
import threading
from pathlib import Path

from config import DATA_DIR
from terminal.core.agent import git_tools, tools
from terminal.core.agent.commands import CommandError, validate_command
from terminal.core.agent.plugin_runner import run_plugin_process
from terminal.core.agent.protocol import (
    ToolCall,
    ToolResult,
    ToolSpec,
)

PLUGIN_DIR = DATA_DIR / "agent_tools"
PLUGIN_NAME = re.compile(r"^[a-z][a-z0-9_]{2,30}$")

_plugin_cache: (
    tuple[tuple[ToolSpec, ...], dict] | None
) = None
_plugin_lock = threading.Lock()

TOOL_SPECS = (
    ToolSpec(
        name="list_dir",
        description="Показать файлы и папки внутри проекта.",
        args={"path": "путь относительно корня проекта, по умолчанию '.'"},
    ),
    ToolSpec(
        name="read_file",
        description=(
            "Прочитать текстовый файл проекта или его часть по строкам. "
            "start — первая строка (с 1), limit — сколько строк."
        ),
        args={
            "path": "путь к файлу относительно корня проекта",
            "start": "номер первой строки, по умолчанию 1",
            "limit": "сколько строк вернуть, по умолчанию весь файл",
        },
        types={"start": "integer", "limit": "integer"},
        required=("path",),
    ),
    ToolSpec(
        name="find_symbol",
        description=(
            "Найти функцию, метод или класс по части имени в индексе "
            "проекта. Быстрее, чем search_text."
        ),
        args={"query": "часть имени, минимум 2 символа"},
        required=("query",),
    ),
    ToolSpec(
        name="search_text",
        description="Найти строку в файлах проекта (регистр не важен).",
        args={
            "query": "искомая строка, минимум 2 символа",
            "path": "где искать, по умолчанию весь проект",
        },
        required=("query",),
    ),
    ToolSpec(
        name="apply_patch",
        description=(
            "Заменить один уникальный фрагмент в файле. "
            "Требует подтверждения пользователя."
        ),
        args={
            "path": "путь к файлу",
            "old": "точный фрагмент, который меняем",
            "new": "чем заменить (пустая строка — удалить)",
        },
        risk="write",
        required=("path", "old", "new"),
    ),
    ToolSpec(
        name="write_file",
        description=(
            "Создать или полностью перезаписать текстовый файл. "
            "Требует подтверждения; лучше apply_patch."
        ),
        args={
            "path": "путь к файлу",
            "content": "полный новый текст файла",
        },
        risk="write",
        required=("path", "content"),
    ),
    ToolSpec(
        name="run_tests",
        description="Запустить pytest в папке проекта и показать итог.",
        args={},
        risk="exec",
    ),
    ToolSpec(
        name="git_status",
        description="Показать состояние рабочей копии git.",
        args={},
        risk="read",
    ),
    ToolSpec(
        name="git_diff",
        description="Показать незакоммиченные изменения.",
        args={"path": "файл или пусто для всего проекта"},
        risk="read",
    ),
    ToolSpec(
        name="git_log",
        description="Показать последние коммиты.",
        args={"limit": "сколько коммитов, по умолчанию 5"},
        risk="read",
    ),
    ToolSpec(
        name="git_commit",
        description=(
            "Закоммитить один или несколько изменённых файлов с сообщением. "
            "Требует подтверждения."
        ),
        args={
            "paths": "список путей к файлам",
            "message": "сообщение коммита",
        },
        types={"paths": "array"},
        risk="write",
        required=("paths", "message"),
    ),
    ToolSpec(
        name="git_restore",
        description=(
            "Откатить незакоммиченные изменения файла. "
            "Требует подтверждения."
        ),
        args={"path": "путь к файлу"},
        risk="write",
        required=("path",),
    ),
    ToolSpec(
        name="run_command",
        description=(
            "Разрешённая команда: git status/diff/log/show, "
            "python -m pytest, python -m compileall."
        ),
        args={"command": "команда одной строкой"},
        risk="exec",
        required=("command",),
    ),
    ToolSpec(
        name="ask_subagent",
        description=(
            "Поручить чтение подзадач отдельным читающим агентам: "
            "они ищут и читают файлы, но не меняют их. Передай task "
            "(одна) или tasks (массив — выполняются параллельно)."
        ),
        args={
            "task": "одна подзадача",
            "tasks": "несколько независимых подзадач (массив)",
        },
        types={"tasks": "array"},
        risk="read",
        required=(),
    ),
    ToolSpec(
        name="update_plan",
        description=(
            "Составить или обновить план задачи. Вызывай в начале "
            "многошаговой задачи и обновляй статусы по ходу."
        ),
        args={"steps": "пункты плана со статусами"},
        risk="read",
        required=("steps",),
        schema={
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "description": "пункты плана по порядку",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "что сделать",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "doing", "done"],
                                "description": "состояние пункта",
                            },
                        },
                        "required": ["text", "status"],
                    },
                }
            },
            "required": ["steps"],
            "additionalProperties": False,
        },
    ),
    ToolSpec(
        name="fetch_url",
        description=(
            "Прочитать веб-страницу по http/https и получить текст без "
            "разметки. Требует подтверждения; локальные адреса запрещены."
        ),
        args={"url": "адрес страницы"},
        risk="exec",
        required=("url",),
    ),
)

PLUGIN_PERMISSIONS = {"fs:read", "fs:write", "net", "exec"}

DEFAULT_PERMISSIONS = {
    "read": ("fs:read",),
    "write": ("fs:read", "fs:write"),
    "exec": ("fs:read", "fs:write", "exec"),
}


def _permissions(document: dict, risk: str) -> tuple[str, ...]:
    """Разрешения плагина: по умолчанию — по уровню риска."""

    raw = document.get("permissions")

    if raw is None:
        return DEFAULT_PERMISSIONS[risk]

    if not isinstance(raw, list) or not all(
        isinstance(item, str) for item in raw
    ):
        raise ValueError("permissions должен быть списком строк.")

    unknown = set(raw) - PLUGIN_PERMISSIONS

    if unknown:
        raise ValueError(
            "Неизвестные разрешения: " + ", ".join(sorted(unknown))
        )

    permissions = tuple(dict.fromkeys(raw))

    if "fs:write" in permissions and risk == "read":
        raise ValueError("fs:write требует risk=write или exec.")

    if "net" in permissions and risk != "exec":
        raise ValueError("net требует risk=exec.")

    if "exec" in permissions and risk != "exec":
        raise ValueError("exec требует risk=exec.")

    return permissions


def _parse_manifest(
    document: object,
    path: Path,
) -> tuple[ToolSpec, Path, str]:
    """Проверяет JSON-манифест, не исполняя код плагина."""

    if not isinstance(document, dict):
        raise ValueError("Манифест должен быть объектом.")

    name = str(document.get("name") or "").strip()

    if not PLUGIN_NAME.fullmatch(name):
        raise ValueError(f"Недопустимое имя плагина: {name}")

    description = str(document.get("description") or "").strip()

    if not description:
        raise ValueError("У плагина нет описания.")

    args = document.get("args") or {}

    if not isinstance(args, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in args.items()
    ):
        raise ValueError("args плагина должен быть словарём строк.")

    required = document.get("required") or ()

    if not isinstance(required, (list, tuple)) or not all(
        isinstance(item, str) and item in args for item in required
    ):
        raise ValueError("required должен ссылаться на args.")

    risk = str(document.get("risk") or "read")

    if risk not in ("read", "write", "exec"):
        raise ValueError("risk должен быть read, write или exec.")

    module = str(document.get("module") or "").strip()

    if not module.endswith(".py"):
        raise ValueError("module должен указывать на .py.")

    module_path = (path.parent / module).resolve()

    if module_path.parent != path.parent.resolve():
        raise ValueError("Модуль плагина должен лежать рядом.")

    if not module_path.is_file():
        raise ValueError(f"Нет модуля плагина: {module}")

    handler = str(document.get("handler") or "handler").strip()

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", handler):
        raise ValueError("Недопустимое имя обработчика.")

    permissions = _permissions(document, risk)

    return (
        ToolSpec(
            name=name,
            description=description,
            args=dict(args),
            risk=risk,
            required=tuple(required),
            permissions=permissions,
        ),
        module_path,
        handler,
    )


def _unsafe_allowed(spec: ToolSpec) -> bool:
    """Плагин с сетью или запуском программ грузится только по разрешению."""

    dangerous = {"net", "exec"} & set(spec.permissions or ())

    if not dangerous:
        return True

    try:
        from terminal.core.agent import settings

        return settings.allow_unsafe_plugins()
    except Exception:  # noqa: BLE001 — без настроек считаем запрещённым
        return False


def plugin_tools() -> tuple[tuple[ToolSpec, ...], dict]:
    """Читает манифесты плагинов, если они разрешены в настройках."""

    global _plugin_cache

    with _plugin_lock:
        if _plugin_cache is not None:
            return _plugin_cache

        specs: list[ToolSpec] = []
        plugins: dict[str, tuple[Path, str]] = {}

        try:
            from terminal.core.agent import settings

            enabled = settings.plugins_enabled()
        except Exception:  # noqa: BLE001 — без настроек плагинов нет
            enabled = False

        if enabled and PLUGIN_DIR.is_dir():
            builtin = {spec.name for spec in TOOL_SPECS}

            for path in sorted(PLUGIN_DIR.glob("*.json")):
                if path.name.startswith("_"):
                    continue

                try:
                    document = json.loads(
                        path.read_text(encoding="utf-8")
                    )
                    spec, module_path, handler = _parse_manifest(
                        document,
                        path,
                    )
                except (OSError, ValueError, json.JSONDecodeError):
                    continue

                if not _unsafe_allowed(spec):
                    continue

                if spec.name in builtin or spec.name in plugins:
                    continue

                specs.append(spec)
                plugins[spec.name] = (
                    module_path,
                    handler,
                    spec.permissions,
                )

        _plugin_cache = (tuple(specs), plugins)

        return _plugin_cache


def reload_plugins() -> None:
    """Сбрасывает кэш плагинов после изменения настроек."""

    global _plugin_cache

    with _plugin_lock:
        _plugin_cache = None


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


def _plugin_handler(name: str):
    """Модуль, обработчик и разрешения плагина."""

    return plugin_tools()[1].get(name)


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


def validate_call(call: ToolCall) -> ToolResult | None:
    """Проверяет аргументы вызова по схеме инструмента."""

    spec = get_spec(call.tool)

    if spec is None:
        return ToolResult(False, f"Неизвестный инструмент: {call.tool}")

    if spec.schema is not None:
        for name in spec.required:
            if name not in call.args:
                return ToolResult(
                    False,
                    f"Не хватает аргумента «{name}».",
                )

        return None

    extra = set(call.args) - set(spec.args)

    if extra:
        return ToolResult(
            False,
            "Лишние аргументы: " + ", ".join(sorted(extra)),
        )

    for name in spec.required:
        if name not in call.args:
            return ToolResult(
                False,
                f"Не хватает аргумента «{name}».",
            )

        value = call.args[name]

        if spec.types.get(name) == "array":
            if (
                not isinstance(value, list)
                or not value
                or not all(
                    isinstance(item, str) and item.strip()
                    for item in value
                )
            ):
                return ToolResult(
                    False,
                    f"Аргумент «{name}» должен быть непустым списком "
                    "строк.",
                )

            continue

        if spec.types.get(name) == "integer":
            if isinstance(value, bool) or not isinstance(
                value, (int, str)
            ):
                return ToolResult(
                    False,
                    f"Аргумент «{name}» должен быть целым числом.",
                )

            try:
                int(value)
            except (TypeError, ValueError):
                return ToolResult(
                    False,
                    f"Аргумент «{name}» должен быть целым числом.",
                )

            continue

        if not isinstance(value, str):
            return ToolResult(
                False,
                f"Аргумент «{name}» должен быть строкой.",
            )

        if not value.strip() and name != "new":
            return ToolResult(
                False,
                f"Аргумент «{name}» не может быть пустым.",
            )

    for name, value in call.args.items():
        if name not in spec.args:
            continue

        if spec.types.get(name) == "array":
            if not isinstance(value, list):
                return ToolResult(
                    False,
                    f"Аргумент «{name}» должен быть списком строк.",
                )

            continue

        if spec.types.get(name) == "integer":
            continue

        if not isinstance(value, str):
            return ToolResult(
                False,
                f"Аргумент «{name}» должен быть строкой.",
            )

    return None


def approval_payload(
    root: Path,
    call: ToolCall,
) -> tuple[str, str, str | None]:
    """Возвращает путь, старый текст и итоговый текст для правки."""

    try:
        if call.tool == "write_file":
            target, old_text, _diff = tools.prepare_write(
                root,
                _string_arg(call, "path"),
                _string_arg(call, "content"),
            )

            return (
                target.relative_to(Path(root).resolve()).as_posix(),
                old_text,
                _string_arg(call, "content"),
            )

        if call.tool == "apply_patch":
            target, old_text, new_text, _diff = tools.prepare_patch(
                root,
                _string_arg(call, "path"),
                _string_arg(call, "old"),
                _string_arg(call, "new"),
            )

            return (
                target.relative_to(Path(root).resolve()).as_posix(),
                old_text,
                new_text,
            )
    except (ToolError, ValueError, OSError):
        return "", "", None

    return "", "", None


def needs_approval(call: ToolCall) -> bool:
    """Требует ли вызов согласия пользователя."""

    spec = get_spec(call.tool)

    return spec is not None and spec.risk != "read"


def preview(root: Path, call: ToolCall) -> ToolResult:
    """Показывает, что именно произойдёт, без выполнения."""

    spec = get_spec(call.tool)

    if spec is None:
        return ToolResult(False, f"Неизвестный инструмент: {call.tool}")

    plugin_handler = _plugin_handler(call.tool)

    if plugin_handler is not None:
        args = json.dumps(call.args, ensure_ascii=False)

        return ToolResult(
            True,
            f"Плагин: {call.tool}\n{args}",
        )

    from terminal.core.agent import mcp

    if call.tool in mcp.mcp_tools()[1]:
        args = json.dumps(call.args, ensure_ascii=False)

        return ToolResult(
            True,
            f"MCP: {call.tool}\n{args}",
        )

    try:
        if call.tool == "write_file":
            _path, _old, diff = tools.prepare_write(
                root,
                _string_arg(call, "path"),
                _string_arg(call, "content"),
            )

            return ToolResult(True, diff)

        if call.tool == "apply_patch":
            _path, _old, _text, diff = tools.prepare_patch(
                root,
                _string_arg(call, "path"),
                _string_arg(call, "old"),
                _string_arg(call, "new"),
            )

            return ToolResult(True, diff)

        if call.tool == "run_tests":
            return ToolResult(
                True,
                "python -m pytest -q\nрабочая папка: " + str(root),
            )

        if call.tool == "git_commit":
            return ToolResult(
                True,
                git_tools.git_preview_commit(
                    root,
                    _string_arg(call, "message"),
                    _list_arg(call, "paths"),
                ),
            )

        if call.tool == "git_restore":
            return ToolResult(
                True,
                git_tools.git_preview_restore(
                    root,
                    _string_arg(call, "path"),
                ),
            )

        if call.tool == "run_command":
            command = _string_arg(call, "command")
            tokens = validate_command(command)

            return ToolResult(True, " ".join(tokens))

        if call.tool == "fetch_url":
            from terminal.core.agent import web

            return web.preview(_string_arg(call, "url"))
    except CommandError as error:
        return ToolResult(False, str(error))
    except ValueError as error:
        return ToolResult(False, str(error))
    except Exception as error:  # noqa: BLE001 — покажем причину
        return ToolResult(False, f"{type(error).__name__}: {error}")

    return ToolResult(True, "Действие без предпросмотра.")


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


def _list_arg(call: ToolCall, name: str) -> list[str]:
    """Список путей: массив или одна строка для совместимости."""

    value = call.args.get(name)

    if isinstance(value, list):
        return [str(item) for item in value]

    if isinstance(value, str) and value.strip():
        return [value]

    return []


def execute(root: Path, call: ToolCall) -> ToolResult:
    """Выполняет вызов инструмента с проверкой аргументов."""

    invalid = validate_call(call)

    if invalid is not None:
        return invalid

    try:
        from terminal.core.agent import mcp

        if call.tool in mcp.mcp_tools()[1]:
            return mcp.call_tool(root, call.tool, call.args)

        plugin_entry = _plugin_handler(call.tool)

        if plugin_entry is not None:
            module_path, handler_name, permissions = plugin_entry

            return run_plugin_process(
                module_path,
                root,
                call.args,
                handler_name,
                permissions=permissions,
            )

        if call.tool == "list_dir":
            return tools.list_dir(
                root,
                _string_arg(call, "path", "."),
            )

        if call.tool == "read_file":
            return tools.read_file(
                root,
                _string_arg(call, "path"),
                _int_arg(call, "start", 1),
                _int_arg(call, "limit", 0),
            )

        if call.tool == "find_symbol":
            from terminal.core.agent import index

            return index.find_symbol(
                root,
                _string_arg(call, "query"),
            )

        if call.tool == "search_text":
            return tools.search_text(
                root,
                _string_arg(call, "query"),
                _string_arg(call, "path", "."),
            )

        if call.tool == "write_file":
            return tools.write_file(
                root,
                _string_arg(call, "path"),
                _string_arg(call, "content"),
            )

        if call.tool == "apply_patch":
            return tools.apply_patch(
                root,
                _string_arg(call, "path"),
                _string_arg(call, "old"),
                _string_arg(call, "new"),
            )

        if call.tool == "run_tests":
            return tools.run_tests(root)

        if call.tool == "git_status":
            return git_tools.git_status(root)

        if call.tool == "git_diff":
            return git_tools.git_diff(
                root,
                _string_arg(call, "path"),
            )

        if call.tool == "git_log":
            return git_tools.git_log(
                root,
                _string_arg(call, "limit", "5"),
            )

        if call.tool == "git_commit":
            return git_tools.git_commit(
                root,
                _string_arg(call, "message"),
                _list_arg(call, "paths"),
            )

        if call.tool == "git_restore":
            return git_tools.git_restore(
                root,
                _string_arg(call, "path"),
            )

        if call.tool == "run_command":
            return tools.run_command(
                root,
                _string_arg(call, "command"),
            )

        if call.tool == "fetch_url":
            from terminal.core.agent import settings, web

            if not settings.browser_enabled():
                return ToolResult(
                    False,
                    "Чтение веб-страниц выключено: включи «Разрешить "
                    "чтение веб-страниц» в окне «Провайдер…».",
                )

            return web.fetch(_string_arg(call, "url"))
    except ValueError as error:
        return ToolResult(False, str(error))
    except Exception as error:  # noqa: BLE001 — ошибку увидит модель
        return ToolResult(
            False,
            f"Инструмент упал: {type(error).__name__}: {error}",
        )

    return ToolResult(False, f"Инструмент не реализован: {call.tool}")
