# Giperion/tests/test_eval_compare.py                                  v001
# Сравнение моделей по истории стенда.

import json

from tools import eval_compare


def _write(path, rows):
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_compare_averages(tmp_path) -> None:
    """Модели сравниваются по последним прогонам."""

    path = tmp_path / "history.jsonl"
    _write(
        path,
        [
            {
                "model": "a",
                "success_rate": 0.5,
                "avg_steps": 6,
                "avg_duration_s": 20,
                "stable_tasks": 10,
                "flaky_tasks": 2,
            },
            {
                "model": "a",
                "success_rate": 1.0,
                "avg_steps": 4,
                "avg_duration_s": 10,
                "stable_tasks": 20,
                "flaky_tasks": 0,
            },
            {
                "model": "b",
                "success_rate": 0.9,
                "avg_steps": 5,
                "avg_duration_s": 15,
                "stable_tasks": 18,
                "flaky_tasks": 1,
            },
        ],
    )

    rows = eval_compare.compare(path, last=5)
    by_model = {row["model"]: row for row in rows}

    assert by_model["a"]["success"] == 0.75
    assert by_model["a"]["steps"] == 5.0
    assert rows[0]["model"] == "b"


def test_last_limits_window(tmp_path) -> None:
    """Учитываются только последние N прогонов."""

    path = tmp_path / "history.jsonl"
    _write(
        path,
        [
            {"model": "a", "success_rate": 0.0},
            {"model": "a", "success_rate": 1.0},
        ],
    )

    rows = eval_compare.compare(path, last=1)

    assert rows[0]["success"] == 1.0
    assert rows[0]["runs"] == 1


def test_empty_history(tmp_path) -> None:
    """Пустая история даёт пустой список."""

    assert eval_compare.compare(tmp_path / "none.jsonl") == []
