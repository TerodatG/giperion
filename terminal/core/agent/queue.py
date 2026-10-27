# Giperion/terminal/core/agent/queue.py                                 v001
# Очередь задач агента: приоритет, статус и результат.
# Последнее изменение: первый вариант — JSON-файл и take/finish.

import threading
from datetime import datetime
from pathlib import Path

from config import DATA_DIR
from shared.storage.json_store import read_json_object, update_json

QUEUE_FILE = DATA_DIR / "agent_queue.json"
MAX_ITEMS = 50
STATUSES = ("pending", "running", "done", "failed")
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load() -> list[dict]:
    """Все пункты очереди."""

    document = read_json_object(QUEUE_FILE)
    raw = document.get("items")

    if not isinstance(raw, list):
        return []

    return [item for item in raw if isinstance(item, dict)]


def _save(items: list[dict]) -> None:
    def mutate(document: dict) -> dict:
        document["items"] = items[-MAX_ITEMS:]

        return document

    update_json(QUEUE_FILE, mutate, default={})


def add(task: str, priority: int = 0, policy: str = "read") -> dict:
    """Добавляет задачу; приоритет больше — раньше."""

    text = " ".join(str(task or "").split())

    if not text:
        raise ValueError("Пустая задача.")

    with _LOCK:
        items = load()

        if len(items) >= MAX_ITEMS:
            raise ValueError(f"Очередь заполнена ({MAX_ITEMS}).")

        item = {
            "id": datetime.now().strftime("%Y%m%d-%H%M%S-%f"),
            "task": text[:500],
            "priority": int(priority),
            "policy": policy if policy in ("read", "confirm", "trust") else "read",
            "status": "pending",
            "created_at": _now(),
            "answer": "",
            "error": "",
        }
        items.append(item)
        _save(items)

    return item


def take() -> dict | None:
    """Берёт самую приоритетную pending-задачу и помечает running."""

    with _LOCK:
        items = load()
        pending = [
            (index, item)
            for index, item in enumerate(items)
            if item.get("status") == "pending"
        ]

        if not pending:
            return None

        index, item = max(
            pending,
            key=lambda pair: (
                int(pair[1].get("priority") or 0),
                pair[1].get("created_at") or "",
            ),
        )
        item["status"] = "running"
        item["started_at"] = _now()
        items[index] = item
        _save(items)

    return item


def finish(
    item_id: str,
    ok: bool,
    answer: str = "",
    error: str = "",
) -> bool:
    """Завершает пункт очереди."""

    with _LOCK:
        items = load()

        for item in items:
            if item.get("id") != item_id:
                continue

            item["status"] = "done" if ok else "failed"
            item["answer"] = str(answer or "")[:4_000]
            item["error"] = str(error or "")[:1_000]
            item["finished_at"] = _now()
            _save(items)

            return True

    return False


def clear(done_only: bool = True) -> int:
    """Удаляет завершённые (или все) пункты."""

    with _LOCK:
        items = load()
        kept = [
            item
            for item in items
            if done_only and item.get("status") in ("pending", "running")
        ]

        if not done_only:
            kept = []

        _save(kept)

    return len(items) - len(kept)


def summary(items: list[dict] | None = None) -> dict:
    """Счётчики по статусам."""

    values = items if items is not None else load()
    result = {status: 0 for status in STATUSES}

    for item in values:
        status = str(item.get("status") or "pending")
        result[status] = result.get(status, 0) + 1

    return result


def file_path() -> Path:
    """Путь к файлу очереди для тестов и CLI."""

    return QUEUE_FILE
