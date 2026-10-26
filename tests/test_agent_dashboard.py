# Giperion/tests/test_agent_dashboard.py                               v001
# HTML-дашборд: карточки, таблица и график.

import json

from tools import agent_dashboard


def _write(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_dashboard_contains_metrics(tmp_path, monkeypatch) -> None:
    """В HTML попадают успех, модель и подтверждения."""

    history = tmp_path / "history.jsonl"
    audit = tmp_path / "audit.jsonl"
    output = tmp_path / "dashboard.html"

    _write(
        history,
        [
            {
                "created_at": "2026-10-27T10:00:00",
                "model": "qwen",
                "passed": 3,
                "total": 4,
                "success_rate": 0.75,
                "avg_steps": 5,
                "avg_duration_s": 12,
                "stable_tasks": 2,
                "flaky_tasks": 1,
            },
            {
                "created_at": "2026-10-27T11:00:00",
                "model": "qwen",
                "passed": 4,
                "total": 4,
                "success_rate": 1.0,
                "avg_steps": 4,
                "avg_duration_s": 10,
                "stable_tasks": 4,
                "flaky_tasks": 0,
            },
        ],
    )
    _write(
        audit,
        [
            {"event": "approval", "payload": {"approved": True}},
            {"event": "approval", "payload": {"approved": False}},
        ],
    )
    monkeypatch.setattr(
        agent_dashboard.schedule,
        "load",
        lambda: [
            {
                "id": "abc",
                "task": "Проверь git",
                "every_minutes": 60,
                "last_run": "",
            }
        ],
    )

    path = agent_dashboard.build(history, audit, output)
    text = path.read_text(encoding="utf-8")

    assert "75 %" in text
    assert "qwen" in text
    assert "Проверь git" in text
    assert "подтверждений" in text
    assert "svg" in text


def test_empty_dashboard_is_valid(tmp_path) -> None:
    """Без истории страница всё равно собирается."""

    output = tmp_path / "empty.html"
    path = agent_dashboard.build(
        tmp_path / "none.jsonl",
        tmp_path / "none.jsonl",
        output,
    )

    assert path.is_file()
    assert "История пуста" in path.read_text(encoding="utf-8")
