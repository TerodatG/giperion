# Giperion/tests/test_agent_limits.py                                  v001
# Лимиты вызовов инструментов на одну задачу.

from types import SimpleNamespace

from terminal.core.agent import loop_tools
from terminal.core.agent.protocol import ToolCall


def _state():
    return SimpleNamespace(
        tool_calls=0,
        network_calls=0,
        write_calls=0,
    )


def test_total_calls_limit() -> None:
    """После лимита вызовов приходит понятная ошибка."""

    state = _state()
    call = ToolCall("list_dir", {"path": "."})

    for _ in range(loop_tools.MAX_TOOL_CALLS):
        assert loop_tools._check_limits(state, call) == ""

    assert "Лимит вызовов" in loop_tools._check_limits(state, call)


def test_network_limit() -> None:
    """Сетевые вызовы ограничены отдельно."""

    state = _state()
    call = ToolCall("fetch_url", {"url": "https://example.com"})

    for _ in range(loop_tools.MAX_NETWORK_CALLS):
        assert loop_tools._check_limits(state, call) == ""

    assert "сетевых" in loop_tools._check_limits(state, call)


def test_write_limit() -> None:
    """Изменяющие вызовы ограничены отдельно."""

    state = _state()
    call = ToolCall("write_file", {"path": "a.txt", "content": "x"})

    for _ in range(loop_tools.MAX_WRITE_CALLS):
        assert loop_tools._check_limits(state, call) == ""

    assert "изменяющих" in loop_tools._check_limits(state, call)
