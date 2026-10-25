# Giperion/tests/test_agent_commands.py                              v001
# Белый список команд агента: shell и разрушительные подкоманды запрещены.

import sys

import pytest

from terminal.core.agent.commands import (
    CommandError,
    validate_command,
)


def test_git_read_is_allowed() -> None:
    """Читающие git-команды проходят проверку."""

    tokens = validate_command("git status --short")

    assert tokens[-2:] == ["status", "--short"]
    assert tokens[0].lower().endswith(".exe") or tokens[0] == "git"


def test_git_push_is_denied() -> None:
    """Пуш и разрушительные подкоманды запрещены."""

    for command in (
        "git push",
        "git reset --hard HEAD",
        "git clean -fd",
        "git checkout .",
    ):
        with pytest.raises(CommandError):
            validate_command(command)


def test_shell_operators_are_denied() -> None:
    """Склейка команд и перенаправления не поддерживаются."""

    for command in (
        "git status && rm -rf .",
        "git diff | more",
        "pytest > out.txt",
        "python -m pytest; echo done",
        "echo $(whoami)",
    ):
        with pytest.raises(CommandError):
            validate_command(command)


def test_python_pytest_is_allowed() -> None:
    """pytest разрешён и через python -m, и напрямую."""

    direct = validate_command("python -m pytest -q")
    short = validate_command("pytest -q")

    assert direct == [sys.executable, "-m", "pytest", "-q"]
    assert short == [sys.executable, "-m", "pytest", "-q"]


def test_arbitrary_python_is_denied() -> None:
    """Произвольный Python-код запускать нельзя."""

    for command in (
        "python -c 1+1",
        "python script.py",
        "python -m pip install x",
    ):
        with pytest.raises(CommandError):
            validate_command(command)


def test_unknown_program_is_denied() -> None:
    """Всё, чего нет в списке, отклоняется."""

    with pytest.raises(CommandError):
        validate_command("powershell Get-Process")

    with pytest.raises(CommandError):
        validate_command("rm -rf .")
