# Giperion/terminal/core/agent/registry.py                          v001
# Реестр read-only инструментов агента и их выполнение.
# Последнее изменение: первый вариант — список, чтение, поиск.

from pathlib import Path

from terminal.core.agent import git_tools, tools
from terminal.core.agent.commands import CommandError, validate_command
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
        required=("path",),
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
            "Закоммитить один файл с сообщением. "
            "Требует подтверждения."
        ),
        args={
            "path": "путь к файлу",
            "message": "сообщение коммита",
        },
        risk="write",
        required=("path", "message"),
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
            "Поручить подзадачу отдельному читающему агенту: "
            "он ищет и читает файлы, но не меняет их."
        ),
        args={"task": "короткая подзадача для подагента"},
        risk="read",
        required=("task",),
    ),
)

_TOOLS = {spec.name: spec for spec in TOOL_SPECS}


def get_spec(name: str) -> ToolSpec | None:
    """Возвращает описание инструмента по имени."""

    return _TOOLS.get(name)


def tool_schemas() -> list[dict]:
    """Отдаёт схемы инструментов в формате function calling."""

    schemas = []

    for spec in TOOL_SPECS:
        properties = {
            name: {
                "type": "string",
                "description": description,
            }
            for name, description in spec.args.items()
        }

        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": list(spec.required),
                        "additionalProperties": False,
                    },
                },
            }
        )

    return schemas


def validate_call(call: ToolCall) -> ToolResult | None:
    """Проверяет аргументы вызова по схеме инструмента."""

    spec = get_spec(call.tool)

    if spec is None:
        return ToolResult(False, f"Неизвестный инструмент: {call.tool}")

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
        if name in spec.args and not isinstance(value, str):
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
                    _string_arg(call, "path"),
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

    invalid = validate_call(call)

    if invalid is not None:
        return invalid

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
                _string_arg(call, "path"),
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
    except ValueError as error:
        return ToolResult(False, str(error))
    except Exception as error:  # noqa: BLE001 — ошибку увидит модель
        return ToolResult(
            False,
            f"Инструмент упал: {type(error).__name__}: {error}",
        )

    return ToolResult(False, f"Инструмент не реализован: {call.tool}")
