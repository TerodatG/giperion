# Giperion/tests/test_agent_parallel.py                                v001
# Параллельные задачи: чтение в основном дереве, запись в worktree.

from types import SimpleNamespace

from tools import agent_parallel


class FakeBrain:
    def fork(self):
        return self


def _result(answer="готово"):
    return SimpleNamespace(
        answer=answer,
        error="",
        cancelled=False,
        steps=[],
    )


def test_run_read_uses_main_tree(monkeypatch, tmp_path) -> None:
    """Чтение не создаёт worktree."""

    calls = {}
    monkeypatch.setattr(agent_parallel, "BASE_DIR", tmp_path)
    monkeypatch.setattr(
        agent_parallel,
        "run_agent",
        lambda task, brain, root, **kwargs: calls.update(
            root=root,
            policy=kwargs.get("policy"),
        )
        or _result(),
    )

    result = agent_parallel.run_read("найди файл", FakeBrain(), 4)

    assert result["ok"]
    assert result["branch"] == ""
    assert calls["root"] == tmp_path
    assert calls["policy"] == "read"


def test_run_write_creates_worktree(monkeypatch, tmp_path) -> None:
    """Запись идёт в отдельную папку и ветку."""

    monkeypatch.setattr(agent_parallel, "BASE_DIR", tmp_path)
    monkeypatch.setattr(
        agent_parallel,
        "create_worktree",
        lambda base, name: (tmp_path / "worktree", "agent/" + name),
    )
    monkeypatch.setattr(
        agent_parallel,
        "run_agent",
        lambda task, brain, root, **kwargs: _result("изменено"),
    )

    result = agent_parallel.run_write(
        "поправь файл",
        FakeBrain(),
        5,
        "confirm",
    )

    assert result["ok"]
    assert result["branch"].startswith("agent/parallel-")
    assert result["answer"] == "изменено"
    assert result["folder"].endswith("worktree")

def test_merge_branches(monkeypatch, tmp_path) -> None:
    """Успешные ветки сливаются через git merge --no-ff."""

    from types import SimpleNamespace

    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)

        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(agent_parallel.subprocess, "run", fake_run)
    monkeypatch.setattr(agent_parallel, "BASE_DIR", tmp_path)

    results = agent_parallel.merge_branches(["agent/a", "agent/b"])

    assert all(code == 0 for _branch, code, _out in results)
    assert any("merge" in command for command in calls)
    assert len(calls) == 2


def test_merge_reports_conflict(monkeypatch, tmp_path) -> None:
    """Конфликт слияния виден по коду."""

    from types import SimpleNamespace

    monkeypatch.setattr(
        agent_parallel.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="CONFLICT",
        ),
    )
    monkeypatch.setattr(agent_parallel, "BASE_DIR", tmp_path)

    results = agent_parallel.merge_branches(["agent/x"])

    assert results[0][1] == 1
    assert "CONFLICT" in results[0][2]
