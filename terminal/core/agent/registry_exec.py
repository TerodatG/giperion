# Giperion/terminal/core/agent/registry_exec.py                       v001
# Проверка вызовов, подтверждения, предпросмотр и выполнение.
# Последнее изменение: вынесено из registry.

import json
from pathlib import Path

from terminal.core.agent import git_tools, tools
from terminal.core.agent.commands import CommandError, validate_command
from terminal.core.agent.plugin_runner import run_plugin_process
from terminal.core.agent.protocol import ToolCall, ToolResult
from terminal.core.agent.registry_plugins import _plugin_handler
from terminal.core.agent.registry_specs import (
    _int_arg,
    _list_arg,
    _string_arg,
    get_spec,
)


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
    except (tools.ToolError, ValueError, OSError):
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

