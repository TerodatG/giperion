# Giperion/tests/test_agent_nightly.py                                  v001
# Ночной отчёт: прогоны, очередь и запись файла.

from tools import agent_nightly


def test_report_contains_runs_and_queue(tmp_path) -> None:
    """Отчёт показывает успех, ошибку и очередь."""

    runs = [
        {"ok": True, "steps": 3, "created_at": "2026-10-27T01:00:00"},
        {
            "ok": False,
            "steps": 2,
            "created_at": "2026-10-27T02:00:00",
            "error": "сбой",
        },
    ]
    path = agent_nightly.write_report(
        runs,
        {"pending": 1, "running": 0, "done": 2, "failed": 1},
        tmp_path / "report.md",
    )
    text = path.read_text(encoding="utf-8")

    assert "Ночной отчёт" in text
    assert "успех: 1" in text
    assert "падений: 1" in text
    assert "сбой" in text
    assert "ждут: 1" in text
    assert "| да | 3 |" in text
