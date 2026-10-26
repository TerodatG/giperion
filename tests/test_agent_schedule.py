# Giperion/tests/test_agent_schedule.py                                v001
# Расписание фоновых задач: добавление, due, отметка и JSONL.

import json
from datetime import datetime, timedelta

import pytest

from terminal.core import schedule


@pytest.fixture(autouse=True)
def _files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        schedule,
        "SCHEDULE_FILE",
        tmp_path / "schedule.json",
    )
    monkeypatch.setattr(
        schedule,
        "RUNS_FILE",
        tmp_path / "runs.jsonl",
    )


def test_add_and_due() -> None:
    """Новая задача пора запускать, после отметки — нет."""

    entry = schedule.add("Проверь статус git", every_minutes=30)

    assert entry["id"]
    assert len(schedule.due()) == 1

    now = datetime(2026, 10, 27, 12, 0, 0)
    schedule.mark_run(entry["id"], now=now)

    assert schedule.due(now=now) == []
    assert len(schedule.due(now=now + timedelta(minutes=31))) == 1


def test_only_read_policy() -> None:
    """Планировщик не разрешает запись и команды."""

    with pytest.raises(ValueError):
        schedule.add("Удали файлы", policy="trust")

    with pytest.raises(ValueError):
        schedule.add("   ")


def test_toggle_and_remove() -> None:
    """Задачу можно выключить и удалить."""

    entry = schedule.add("Проверь тесты", every_minutes=5)

    assert schedule.set_enabled(entry["id"], False)
    assert schedule.due() == []
    assert schedule.set_enabled(entry["id"], True)
    assert schedule.remove(entry["id"])
    assert not schedule.remove(entry["id"])


def test_record_result_jsonl() -> None:
    """Итог запуска дописывается в JSONL."""

    schedule.record_result({"id": "abc", "ok": True})

    line = schedule.RUNS_FILE.read_text(encoding="utf-8").strip()
    payload = json.loads(line)

    assert payload["id"] == "abc"
    assert payload["ok"] is True
    assert payload["ts"]
