# Giperion/terminal/core/agent/loop_audit.py                          v001
# Аудит вызовов внутри цикла: событие и короткая цель.
# Последнее изменение: вынесено из loop_tools.

from terminal.core.agent.protocol import ToolCall


def audit(event: str, payload: dict) -> dict | None:
    """Пишет событие аудита, не ломая задачу при сбое журнала."""

    try:
        from terminal.core.agent import audit as journal

        return journal.record(event, payload)
    except (OSError, TypeError, ValueError):
        return None


def target(call: ToolCall) -> str:
    """Короткая цель вызова для аудита."""

    try:
        from terminal.core.agent import audit as journal

        return journal.target_of(dict(call.args or {}))
    except (TypeError, ValueError):
        return ""
