# Giperion/tests/test_agent_stats.py                                 v001
# Числовые показатели развития агента: прогоны, ресурсы и уровень.
# Последнее изменение: первый набор — подсчёт по журналу прогонов.

import json

import pytest

from terminal.core import agent_stats
from terminal.core.agent import runs


@pytest.fixture()
def runs_file(tmp_path, monkeypatch):
    """Изолирует журнал прогонов агента."""

    path = tmp_path / "agent_runs.jsonl"

    monkeypatch.setattr(runs, "RUNS_FILE", path)

    return path


def write_runs(path, records: list[dict]) -> None:
    """Пишет журнал прогонов для проверки."""

    path.write_text(
        "\n".join(
            json.dumps(record, ensure_ascii=False)
            for record in records
        )
        + "\n",
        encoding="utf-8",
    )


def test_empty_journal_gives_zero_stats(runs_file) -> None:
    """Без прогонов уровень первый, опыт нулевой."""

    stats = agent_stats.read_agent_stats()

    assert stats["runs_total"] == 0
    assert stats["runs_ok"] == 0
    assert stats["success_percent"] == 0
    assert stats["experience"] == 0
    assert stats["level"] == 1
    assert stats["level_progress"] == 0
    assert stats["last_run"] == ""


def test_stats_count_work_and_level(runs_file) -> None:
    """Прогоны, шаги, файлы и опыт считаются по журналу."""

    write_runs(
        runs_file,
        [
            {
                "created_at": "2026-10-25T10:00:00",
                "steps": 4,
                "approvals": 1,
                "duration_s": 10.0,
                "files": ["a.py"],
                "tokens": 100,
                "cost": 0.5,
            },
            {
                "created_at": "2026-10-25T11:00:00",
                "steps": 6,
                "duration_s": 20.0,
                "files": ["a.py", "b.py"],
                "tokens": 200,
                "cost": 0.25,
            },
            {
                "created_at": "2026-10-25T12:00:00",
                "steps": 2,
                "duration_s": 5.0,
                "tokens": 50,
                "error": "boom",
            },
            {
                "created_at": "2026-10-25T13:00:00",
                "steps": 1,
                "duration_s": 1.0,
                "cancelled": True,
            },
        ],
    )

    stats = agent_stats.read_agent_stats()

    assert stats["runs_total"] == 4
    assert stats["runs_ok"] == 2
    assert stats["runs_failed"] == 1
    assert stats["runs_cancelled"] == 1
    assert stats["success_percent"] == 50
    assert stats["steps_total"] == 13
    assert stats["files_total"] == 2
    assert stats["approvals_total"] == 1
    assert stats["tokens_total"] == 350
    assert stats["cost_total"] == pytest.approx(0.75)
    assert stats["duration_total"] == pytest.approx(36.0)
    assert stats["duration_average"] == pytest.approx(9.0)

    # Опыт: 2 успешных прогона, 13 шагов, 2 файла.
    assert stats["experience"] == 2 * 10 + 13 * 2 + 2 * 5
    assert stats["level"] == 1
    assert stats["level_progress"] == 11
    assert stats["to_next_level"] == 444
    assert stats["last_run"] == "25.10.2026 13:00"


def test_level_grows_with_experience(runs_file) -> None:
    """Много успешных прогонов поднимают уровень."""

    records = [
        {
            "created_at": "2026-10-25T10:00:00",
            "steps": 10,
            "duration_s": 10.0,
            "files": [f"file-{index}.py"],
        }
        for index in range(40)
    ]

    write_runs(runs_file, records)

    stats = agent_stats.read_agent_stats()

    # 40 * 10 + 400 * 2 + 40 * 5 = 1400 опыта.
    assert stats["experience"] == 1400
    assert stats["level"] == 3
    assert stats["level_progress"] == 80


def test_formats() -> None:
    """Единицы времени, стоимости и даты читаются по-русски."""

    assert agent_stats.format_duration(0) == "0 с"
    assert agent_stats.format_duration(19.2) == "19 с"
    assert agent_stats.format_duration(0.082) == "82 мс"
    assert agent_stats.format_duration(75) == "1 мин 15 с"
    assert agent_stats.format_duration(3725) == "1 ч 2 мин"

    assert agent_stats.format_cost(0) == "—"
    assert agent_stats.format_cost(0.75) == "$ 0,75"

    assert (
        agent_stats.format_stamp("2026-10-25T13:00:00")
        == "25.10.2026 13:00"
    )
    assert agent_stats.format_stamp("") == ""
