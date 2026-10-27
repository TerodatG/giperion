# Giperion/tests/test_agent_dag.py                                      v001
# Граф задач: порядок, цикл и пропуск потомков.

import pytest

from tools import agent_dag


def test_validate_orders_dependencies() -> None:
    """Зависимости идут раньше потомков."""

    order = agent_dag.validate(
        [
            {"id": "c", "depends": ["b"]},
            {"id": "a"},
            {"id": "b", "depends": ["a"]},
        ]
    )

    assert order == ["a", "b", "c"]


def test_cycle_is_rejected() -> None:
    """Цикл не принимается."""

    with pytest.raises(ValueError, match="цикл"):
        agent_dag.validate(
            [
                {"id": "a", "depends": ["b"]},
                {"id": "b", "depends": ["a"]},
            ]
        )


def test_unknown_dependency_is_rejected() -> None:
    """Неизвестная зависимость — ошибка."""

    with pytest.raises(ValueError, match="неизвестной"):
        agent_dag.validate([{"id": "a", "depends": ["nope"]}])


def test_run_passes_results_in_order() -> None:
    """Задачи выполняются уровни за уровнем."""

    seen: list[str] = []

    def runner(item):
        seen.append(item["id"])

        return {"ok": True, "answer": item["task"]}

    results = agent_dag.run(
        [
            {"id": "b", "task": "второй", "depends": ["a"]},
            {"id": "a", "task": "первый"},
        ],
        runner,
        workers=2,
    )

    assert [item["id"] for item in results] == ["a", "b"]
    assert seen == ["a", "b"]
    assert results[1]["answer"] == "второй"


def test_failed_dependency_skips_child() -> None:
    """Потомок упавшей задачи не запускается."""

    calls: list[str] = []

    def runner(item):
        calls.append(item["id"])

        return {"ok": False, "error": "сбой"}

    results = agent_dag.run(
        [
            {"id": "a"},
            {"id": "b", "depends": ["a"]},
        ],
        runner,
    )

    assert calls == ["a"]
    assert results[1]["skipped"]
    assert "зависимость" in results[1]["error"]
