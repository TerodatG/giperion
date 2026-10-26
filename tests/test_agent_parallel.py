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
