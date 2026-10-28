# Giperion/tests/test_agent_ab.py                                       v001
# A/B-прогон: сводка и сравнение двух результатов.

from types import SimpleNamespace

from terminal.core.agent import ab


def _result(answer, tokens, cost):
    return SimpleNamespace(
        answer=answer,
        error="",
        cancelled=False,
        steps=[1, 2],
        usage=[{"step": 1, "tokens": tokens, "cost": cost}],
    )


def test_summarize_counts_usage() -> None:
    """Сводка складывает токены и стоимость."""

    item = ab.summarize(_result("ок", 120, 0.002))

    assert item["ok"]
    assert item["steps"] == 2
    assert item["tokens"] == 120
    assert item["cost"] == 0.002


def test_compare_runs_both(monkeypatch, tmp_path) -> None:
    """A/B вызывает оба мозга на одной задаче."""

    results = [
        _result("A", 100, 0.001),
        _result("B", 200, 0.002),
    ]
    calls = []

    def fake_run(task, brain, root, **kwargs):
        calls.append((task, brain, root))

        return results.pop(0)

    monkeypatch.setattr(ab, "run_agent", fake_run)

    result = ab.compare("задача", "brain-a", "brain-b", tmp_path)

    assert result["a"]["answer"] == "A"
    assert result["b"]["tokens"] == 200
    assert [call[1] for call in calls] == ["brain-a", "brain-b"]
