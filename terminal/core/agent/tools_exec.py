# Giperion/terminal/core/agent/tools_exec.py                           v001
# Тесты и разрешённые команды без shell.
# Последнее изменение: вынесено из tools.

import sys
from pathlib import Path

from shared.action_log import add_action
from terminal.core.agent import exec_sandbox
from terminal.core.agent.commands import CommandError, validate_command
from terminal.core.agent.protocol import ToolResult
from terminal.core.agent.tools_policy import TEST_TIMEOUT, _root


def run_tests(root: Path, dry_run: bool = False) -> ToolResult:
    """Запускает pytest в папке проекта и отдаёт хвост вывода."""

    base = _root(root)

    if dry_run:
        return ToolResult(
            True,
            f"Будет выполнено в {base.name}: python -m pytest -q",
        )

    result = exec_sandbox.run_python(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        base,
        TEST_TIMEOUT,
    )

    if result.timed_out:
        return ToolResult(False, result.output)

    output = result.output or "вывод пуст"
    tail = output[-4000:]
    ok = result.code == 0
    mode = " · AppContainer" if result.isolated else ""

    add_action(
        "Агент: pytest, код "
        f"{result.code}{mode}"
    )

    return ToolResult(
        ok,
        f"pytest: код {result.code}{mode}\n{tail}",
    )


def run_command(
    root: Path,
    command: str,
    dry_run: bool = False,
) -> ToolResult:
    """Выполняет команду из белого списка в ограниченном окружении."""

    try:
        tokens = validate_command(command)
    except CommandError as error:
        return ToolResult(False, str(error))

    if dry_run:
        return ToolResult(
            True,
            "Будет выполнено: " + " ".join(tokens),
        )

    base = _root(root)

    if exec_sandbox.is_python(tokens):
        result = exec_sandbox.run_python(tokens, base, TEST_TIMEOUT)
    else:
        result = exec_sandbox.run(tokens, base, TEST_TIMEOUT)

    if result.timed_out:
        return ToolResult(False, result.output)

    output = result.output or "вывод пуст"
    tail = output[-4000:]
    mode = " · AppContainer" if result.isolated else ""

    add_action(
        "Агент: команда " + " ".join(tokens[:3]) + mode
    )

    return ToolResult(
        result.code == 0,
        f"код {result.code}{mode}\n{tail}",
    )

