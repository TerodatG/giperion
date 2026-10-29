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
    _bool_arg,
    _int_arg,
    _list_arg,
    _string_arg,
    get_spec,
)


def _missing_required(call: ToolCall, spec) -> ToolResult | None:
    """Проверяет наличие обязательных аргументов."""

    for name in spec.required:
        if name not in call.args:
            return ToolResult(False, f"Не хватает аргумента «{name}».")

    return None


def _value_error(
    name: str,
    value,
    spec,
    *,
    required: bool,
) -> ToolResult | None:
    """Проверяет тип и пустоту одного аргумента."""

    kind = spec.types.get(name)

    if kind == "array":
        if (
            not isinstance(value, list)
            or (required and not value)
            or not all(
                isinstance(item, str) and item.strip()
                for item in value
            )
        ):
            return ToolResult(
                False,
                f"Аргумент «{name}» должен быть непустым списком строк."
                if required
                else f"Аргумент «{name}» должен быть списком строк.",
            )

        return None

    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, (int, str)):
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

        return None

    if not isinstance(value, str):
        return ToolResult(
            False,
            f"Аргумент «{name}» должен быть строкой.",
        )

    if required and not value.strip() and name != "new":
        return ToolResult(
            False,
            f"Аргумент «{name}» не может быть пустым.",
        )

    return None


def validate_call(call: ToolCall) -> ToolResult | None:
    """Проверяет аргументы вызова по схеме инструмента."""

    spec = get_spec(call.tool)

    if spec is None:
        return ToolResult(False, f"Неизвестный инструмент: {call.tool}")

    missing = _missing_required(call, spec)

    if missing is not None:
        return missing

    if spec.schema is not None:
        return None

    extra = set(call.args) - set(spec.args)

    if extra:
        return ToolResult(
            False,
            "Лишние аргументы: " + ", ".join(sorted(extra)),
        )

    for name in spec.required:
        error = _value_error(
            name,
            call.args[name],
            spec,
            required=True,
        )

        if error is not None:
            return error

    for name, value in call.args.items():
        if name in spec.args and name not in spec.required:
            error = _value_error(
                name,
                value,
                spec,
                required=False,
            )

            if error is not None:
                return error

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

        if call.tool == "browser_read":
            return ToolResult(
                True,
                "Открыть страницу в браузере с JavaScript\n"
                + _string_arg(call, "url"),
            )

        if call.tool == "browser_act":
            actions = call.args.get("actions")
            count = len(actions) if isinstance(actions, list) else 0

            return ToolResult(
                True,
                f"Открыть страницу и выполнить действий: {count}\n"
                + _string_arg(call, "url"),
            )

        if call.tool == "remember":
            return ToolResult(
                True,
                "Записать в память проекта:\n"
                + _string_arg(call, "text"),
            )
    except CommandError as error:
        return ToolResult(False, str(error))
    except ValueError as error:
        return ToolResult(False, str(error))
    except Exception as error:  # noqa: BLE001 — покажем причину
        return ToolResult(False, f"{type(error).__name__}: {error}")

    return ToolResult(True, "Действие без предпросмотра.")


def _file_tool(root: Path, call: ToolCall) -> ToolResult | None:
    """Файловые инструменты."""

    if call.tool == "list_dir":
        return tools.list_dir(root, _string_arg(call, "path", "."))

    if call.tool == "read_file":
        return tools.read_file(
            root,
            _string_arg(call, "path"),
            _int_arg(call, "start", 1),
            _int_arg(call, "limit", 0),
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

    return None


def _git_tool(root: Path, call: ToolCall) -> ToolResult | None:
    """Инструменты git."""

    if call.tool == "git_status":
        return git_tools.git_status(root)

    if call.tool == "git_diff":
        return git_tools.git_diff(root, _string_arg(call, "path"))

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

    return None


def _special_tool(root: Path, call: ToolCall) -> ToolResult | None:
    """MCP, плагины, индекс, тесты, команды и веб."""

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

    if call.tool == "find_symbol":
        from terminal.core.agent import index

        return index.find_symbol(root, _string_arg(call, "query"))

    if call.tool == "find_relevant":
        from terminal.core.agent import semantic

        return semantic.find_relevant(
            root,
            _string_arg(call, "query"),
            _int_arg(call, "limit", semantic.DEFAULT_LIMIT),
        )

    if call.tool.startswith("lsp_"):
        from terminal.core.agent import lsp_tools

        path = _string_arg(call, "path")

        if call.tool == "lsp_diagnostics":
            return lsp_tools.diagnostics(root, path)

        if call.tool == "lsp_symbols":
            return lsp_tools.symbols(root, path)

        line = _int_arg(call, "line")
        character = _int_arg(call, "character")

        if call.tool == "lsp_definition":
            return lsp_tools.definition(root, path, line, character)

        if call.tool == "lsp_hover":
            return lsp_tools.hover(root, path, line, character)

        return lsp_tools.references(root, path, line, character)

    if call.tool == "remember":
        from terminal.core.agent import memory

        try:
            line = memory.add_note(
                _string_arg(call, "text"),
                root=root,
            )
        except ValueError as error:
            return ToolResult(False, str(error))

        return ToolResult(True, "Запомнено: " + line)

    if call.tool == "run_tests":
        return tools.run_tests(
            root,
            dry_run=_bool_arg(call, "dry_run"),
        )

    if call.tool == "run_command":
        return tools.run_command(
            root,
            _string_arg(call, "command"),
            dry_run=_bool_arg(call, "dry_run"),
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

    if call.tool == "browser_read":
        from terminal.core.agent import browser_js

        return browser_js.read(
            root,
            _string_arg(call, "url"),
            _string_arg(call, "wait"),
        )

    if call.tool == "browser_act":
        from terminal.core.agent import browser_js

        actions = call.args.get("actions")

        if not isinstance(actions, list):
            return ToolResult(
                False,
                "Аргумент «actions» должен быть списком действий.",
            )

        record = _string_arg(call, "record")
        kwargs = {"record": record} if record else {}

        return browser_js.act(
            root,
            _string_arg(call, "url"),
            actions,
            _string_arg(call, "wait"),
            bool(call.args.get("shot")),
            full_page=bool(call.args.get("full_page")),
            **kwargs,
        )

    return None


def execute(root: Path, call: ToolCall) -> ToolResult:
    """Выполняет вызов инструмента с проверкой аргументов."""

    invalid = validate_call(call)

    if invalid is not None:
        return invalid

    try:
        for handler in (_special_tool, _file_tool, _git_tool):
            result = handler(root, call)

            if result is not None:
                return result
    except ValueError as error:
        return ToolResult(False, str(error))
    except Exception as error:  # noqa: BLE001 — ошибку увидит модель
        return ToolResult(
            False,
            f"Инструмент упал: {type(error).__name__}: {error}",
        )

    return ToolResult(False, f"Инструмент не реализован: {call.tool}")
