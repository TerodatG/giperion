# Giperion/tests/test_agent_service.py                                  v001
# Служба Windows: команда sc.exe и dry-run.

import pytest

from tools import agent_service


def test_command_contains_daemon_and_interval() -> None:
    """binPath запускает демон с нужным интервалом."""

    command = agent_service.command_for(120, python="python.exe")

    assert command[:3] == [
        "sc",
        "create",
        agent_service.SERVICE_NAME,
    ]
    assert any("tools.agent_daemon" in item for item in command)
    assert any("120" in item for item in command)


def test_install_dry_run() -> None:
    """dry-run не вызывает sc."""

    code, output = agent_service.install(60, dry_run=True)

    assert code == 0
    assert "sc create" in output
    assert agent_service.SERVICE_NAME in output


def test_remove_and_control_dry_run() -> None:
    """remove/start/stop/query собирают команды."""

    assert agent_service.remove(dry_run=True)[1].startswith("sc delete")
    assert agent_service.control("start", dry_run=True)[1].startswith(
        "sc start"
    )
    assert agent_service.control("query", dry_run=True)[1].startswith(
        "sc query"
    )


def test_unknown_action() -> None:
    """Неизвестное действие отклоняется."""

    with pytest.raises(ValueError):
        agent_service.control("boom")
