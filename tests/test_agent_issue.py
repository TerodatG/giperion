# Giperion/tests/test_agent_issue.py                                    v001
# Issue → задача: GitHub CLI и GitLab REST.

import json
from types import SimpleNamespace

from tools import agent_issue


def test_fetch_github(monkeypatch) -> None:
    """gh issue view разбирается в номер, заголовок и тело."""

    def fake_run(command, **kwargs):
        assert command[:3] == ["gh", "issue", "view"]
        assert "--repo" in command

        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {"number": 7, "title": "Баг", "body": "Описание"},
                ensure_ascii=False,
            ),
            stderr="",
        )

    monkeypatch.setattr(agent_issue.subprocess, "run", fake_run)

    issue = agent_issue.fetch_github(7, "org/repo")

    assert issue == {
        "number": 7,
        "title": "Баг",
        "body": "Описание",
    }
    assert agent_issue.task_text(issue) == "Баг\n\nОписание"


def test_fetch_github_error(monkeypatch) -> None:
    """Ошибка gh не превращается в пустую задачу."""

    monkeypatch.setattr(
        agent_issue.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="not found",
        ),
    )

    try:
        agent_issue.fetch_github(1)
    except ValueError as error:
        assert "not found" in str(error)
    else:
        raise AssertionError("ожидалась ошибка")


def test_fetch_gitlab(monkeypatch) -> None:
    """GitLab REST отдаёт iid/description."""

    class Response:
        def read(self, limit=0):
            return json.dumps(
                {
                    "iid": 3,
                    "title": "Задача",
                    "description": "Текст",
                },
                ensure_ascii=False,
            ).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        agent_issue.urllib.request,
        "urlopen",
        lambda request, timeout=0: Response(),
    )

    issue = agent_issue.fetch_gitlab(3, "group/project", token="secret")

    assert issue["number"] == 3
    assert issue["title"] == "Задача"
    assert issue["body"] == "Текст"


def test_create_branch_uses_issue_slug(monkeypatch, tmp_path) -> None:
    """Ветка из issue называется agent/issue-<номер>-<слаг>."""

    calls = {}

    def fake_create(root, name):
        calls.update(root=root, name=name)

        return tmp_path / "worktree", "agent/" + name

    monkeypatch.setattr(
        "terminal.core.agent.worktrees.create_worktree",
        fake_create,
    )

    folder, branch = agent_issue.create_branch(
        {"number": 12, "title": "Fix Login Form"},
        tmp_path,
    )

    assert calls["name"] == "issue-12-fix-login-form"
    assert branch == "agent/issue-12-fix-login-form"
    assert folder == tmp_path / "worktree"


def test_run_issue_commits_and_creates_pr(monkeypatch, tmp_path) -> None:
    """Сквозной сценарий: ветка, агент, коммит, PR."""

    from types import SimpleNamespace

    issue = {"number": 5, "title": "Fix bug", "body": "Details"}
    calls = {}

    monkeypatch.setattr(
        agent_issue,
        "create_branch",
        lambda value: (tmp_path / "wt", "agent/issue-5-fix-bug"),
    )
    monkeypatch.setattr(
        "tools.eval_runner.build_brain",
        lambda model, provider: (object(), "test/model"),
    )
    monkeypatch.setattr(
        "terminal.core.agent.loop.run_agent",
        lambda *args, **kwargs: SimpleNamespace(
            answer="готово",
            error="",
            cancelled=False,
            steps=[1],
        ),
    )
    monkeypatch.setattr(
        agent_issue,
        "_commit_all",
        lambda folder, message: calls.update(
            commit=(folder, message)
        )
        or True,
    )
    monkeypatch.setattr(
        "tools.agent_pr.publish",
        lambda branch, title, body: calls.update(
            pr=(branch, title, body)
        )
        or [("pr", 0, "ok")],
    )

    result = agent_issue.run_issue(issue, create_pr=True)

    assert result["ok"]
    assert result["committed"]
    assert result["branch"] == "agent/issue-5-fix-bug"
    assert calls["commit"][1].startswith("issue #5")
    assert calls["pr"][0] == "agent/issue-5-fix-bug"
