# Giperion/tests/test_agent_queue.py                                    v001
# Очередь задач: приоритет, статусы и очистка.

import pytest

from terminal.core.agent import queue


@pytest.fixture(autouse=True)
def _file(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, "QUEUE_FILE", tmp_path / "queue.json")


def test_add_and_take_priority() -> None:
    """Берётся задача с большим приоритетом."""

    queue.add("низкий", priority=1)
    high = queue.add("высокий", priority=9)

    item = queue.take()

    assert item is not None
    assert item["id"] == high["id"]
    assert item["status"] == "running"
    assert queue.take()["task"] == "низкий"
    assert queue.take() is None


def test_finish_and_summary() -> None:
    """Завершение пишет статус и ответ."""

    item = queue.add("задача")
    taken = queue.take()
    assert taken["id"] == item["id"]

    assert queue.finish(item["id"], True, "готово")
    assert not queue.finish("missing", True)

    stats = queue.summary()

    assert stats["done"] == 1
    assert stats["pending"] == 0


def test_clear_only_finished() -> None:
    """Очистка по умолчанию оставляет незавершённые."""

    first = queue.add("готовая")
    queue.take()
    queue.finish(first["id"], True)
    queue.add("ждёт")

    assert queue.clear() == 1
    assert [item["task"] for item in queue.load()] == ["ждёт"]

    assert queue.clear(done_only=False) == 1
    assert queue.load() == []


def test_empty_task_rejected() -> None:
    """Пустая задача не добавляется."""

    with pytest.raises(ValueError):
        queue.add("   ")
