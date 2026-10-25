# Giperion/terminal/core/agent/registry.py                          v001
# Реестр read-only инструментов агента и их выполнение.
# Последнее изменение: первый вариант — список, чтение, поиск.

from pathlib import Path

from terminal.core.agent import tools
from terminal.core.agent.protocol import (
    ToolCall,
    ToolResult,
    ToolSpec,
)

TOOL_SPECS = (
    ToolSpec(
        name="list_dir",
        description="Показать файлы и папки внутри проекта.",
        args={"path": "путь относительно корня проекта, по умолчанию '.'"},
    ),
    ToolSpec(
        name="read_file",
        description="Прочитать текстовый файл проекта.",
        args={"path": "путь к файлу относительно корня проекта"},
    ),
    ToolSpec(
        name="search_text",
        description="Найти строку в файлах проекта (регистр не важен).",
        args={
            "query": "искомая строка, минимум 2 символа",
            "path": "где искать, по умолчанию весь проект",
        },
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
    ),
    ToolSpec(
        name="run_tests",
        description="Запустить pytest в папке проекта и показать итог.",
        args={},
        risk="exec",
    ),
)

_TOOLS = {spec.name: spec for spec in TOOL_SPECS}


def get_spec(name: str) -> ToolSpec | None:
    """Возвращает описание инструмента по имени."""

    return _TOOLS.get(name)


def needs_approval(call: ToolCall) -> bool:
    """Требует ли вызов согласия пользователя."""

    spec = get_spec(call.tool)

    return spec is not None and spec.risk != "read"


def preview(root: Path, call: ToolCall) -> ToolResult:
    """Показывает, что именно произойдёт, без выполнения."""

    spec = get_spec(call.tool)

    if spec is None:
        return ToolResult(False, f"Неизвестный инструмент: {call.tool}")

    try:
        if call.tool == "write_file":
            _path, _old, diff = tools.prepare_write(
                root,
                _string_arg(call, "path"),
                _string_arg(call, "content"),
            )

            return ToolResult(True, diff)

        if call.tool == "apply_patch":
            _path, _text, diff = tools.prepare_patch(
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
    except ValueError as error:
        return ToolResult(False, str(error))
    except Exception as error:  # noqa: BLE001 — покажем причину
        return ToolResult(False, f"{type(error).__name__}: {error}")

    return ToolResult(True, "Действие без предпросмотра.")


def tools_prompt() -> str:
    """Описывает инструменты так, как их увидит модель."""

    lines = []

    for spec in TOOL_SPECS:
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


def execute(root: Path, call: ToolCall) -> ToolResult:
    """Выполняет вызов инструмента с проверкой аргументов."""

    spec = get_spec(call.tool)

    if spec is None:
        return ToolResult(False, f"Неизвестный инструмент: {call.tool}")

    extra = set(call.args) - set(spec.args)

    if extra:
        return ToolResult(
            False,
            "Лишние аргументы: " + ", ".join(sorted(extra)),
        )

    try:
        if call.tool == "list_dir":
            return tools.list_dir(
                root,
                _string_arg(call, "path", "."),
            )

        if call.tool == "read_file":
            return tools.read_file(
                root,
                _string_arg(call, "path"),
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
    except ValueError as error:
        return ToolResult(False, str(error))
    except Exception as error:  # noqa: BLE001 — ошибку увидит модель
        return ToolResult(
            False,
            f"Инструмент упал: {type(error).__name__}: {error}",
        )

    return ToolResult(False, f"Инструмент не реализован: {call.tool}")
