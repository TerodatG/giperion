# Giperion/tests/test_agent_daemon.py                                  v001
# Демон расписания: пустой и непустой due.

from tools import agent_daemon


def test_tick_skips_when_empty(monkeypatch) -> None:
    """Без due-задач демон ничего не запускает."""

    calls: list[int] = []
    monkeypatch.setattr(agent_daemon.schedule, "due", lambda: [])
    monkeypatch.setattr(
        agent_daemon,
        "run_due",
        lambda limit=2: calls.append(limit) or 0,
    )

    assert agent_daemon.tick(3) is False
    assert calls == []


def test_tick_runs_due(monkeypatch) -> None:
    """При наличии задач вызывается run-due."""

    calls: list[int] = []
    monkeypatch.setattr(
        agent_daemon.schedule,
        "due",
        lambda: [{"id": "a", "task": "проверь"}],
    )
    monkeypatch.setattr(
        agent_daemon,
        "run_due",
        lambda limit=2: calls.append(limit) or 0,
    )

    assert agent_daemon.tick(2) is True
    assert calls == [2]
