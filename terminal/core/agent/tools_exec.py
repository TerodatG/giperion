# Giperion/terminal/core/agent/tools_exec.py                           v001
# Тесты и разрешённые команды без shell.
# Последнее изменение: вынесено из tools.

import subprocess
import sys
from pathlib import Path

from shared.action_log import add_action
from terminal.core.agent.commands import CommandError, validate_command
from terminal.core.agent.protocol import ToolResult
from terminal.core.agent.tools_policy import TEST_TIMEOUT, _root


def run_tests(root: Path) -> ToolResult:
    """Запускает pytest в папке проекта и отдаёт хвост вывода."""

    base = _root(root)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=base,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEST_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            False,
            f"Тесты не успели за {TEST_TIMEOUT} секунд.",
        )
    except OSError as error:
        return ToolResult(False, f"Не удалось запустить тесты: {error}")

    output = (result.stdout + result.stderr).strip()
    tail = output[-4000:] if output else "вывод пуст"
    ok = result.returncode == 0

    add_action(
        "Агент: pytest, код "
        f"{result.returncode}"
    )

    return ToolResult(
        ok,
        f"pytest: код {result.returncode}\n{tail}",
    )


def run_command(root: Path, command: str) -> ToolResult:
    """Выполняет команду из белого списка без shell."""

    try:
        tokens = validate_command(command)
    except CommandError as error:
        return ToolResult(False, str(error))

    base = _root(root)

    try:
        result = subprocess.run(
            tokens,
            cwd=base,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEST_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            False,
            f"Команда не успела за {TEST_TIMEOUT} секунд.",
        )
    except OSError as error:
        return ToolResult(False, f"Не удалось выполнить: {error}")

    output = (result.stdout + result.stderr).strip()
    tail = output[-4000:] if output else "вывод пуст"

    add_action(
        "Агент: команда " + " ".join(tokens[:3])
    )

    return ToolResult(
        result.returncode == 0,
        f"код {result.returncode}\n{tail}",
    )

