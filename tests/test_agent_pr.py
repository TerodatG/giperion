# Giperion/tests/test_agent_pr.py                                      v001
# Публикация ветки: push, gh и сухой прогон.

from types import SimpleNamespace

from tools import agent_pr


def test_publish_runs_push_and_pr(monkeypatch) -> None:
    """Команды push и gh pr create вызываются по порядку."""

    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)

        return SimpleNamespace(
            returncode=0,
            stdout="ok",
            stderr="",
        )

    monkeypatch.setattr(agent_pr.subprocess, "run", fake_run)
    monkeypatch.setattr(agent_pr.shutil, "which", lambda name: "gh")

    steps = agent_pr.publish(
        "agent/task-1",
        "Задача 1",
        "Описание",
    )

    assert all(code == 0 for _name, code, _out in steps)
    assert any("push" in command for command in calls)
    assert any("gh" in command[0] for command in calls)


def test_dry_run_does_not_call(monkeypatch) -> None:
    """Сухой прогон только печатает команды."""

    calls: list = []
    monkeypatch.setattr(
        agent_pr.subprocess,
        "run",
        lambda *args, **kwargs: calls.append(args),
    )
    monkeypatch.setattr(agent_pr.shutil, "which", lambda name: "gh")

    steps = agent_pr.publish(
        "agent/task-2",
        "Задача 2",
        dry_run=True,
    )

    assert not calls
    assert all(code == 0 for _name, code, _out in steps)
    assert any("gh pr create" in output for _n, _c, output in steps)


def test_missing_gh_is_reported(monkeypatch) -> None:
    """Без GitHub CLI шаг PR возвращает ошибку."""

    monkeypatch.setattr(agent_pr.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        agent_pr.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    steps = agent_pr.publish("agent/x", "X")
    pr_step = [item for item in steps if item[0] == "pr"][0]

    assert pr_step[1] == 1
    assert "gh" in pr_step[2]
