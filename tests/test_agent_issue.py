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
