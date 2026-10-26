# Giperion/terminal/core/schedule.py                                    v001
# Расписание фоновых read-only задач агента.
# Последнее изменение: первый вариант — add/remove/due и отметка запуска.

import json
import uuid
from datetime import datetime, timedelta

from config import DATA_DIR
from shared.storage.json_store import read_json_object, write_json

SCHEDULE_FILE = DATA_DIR / "agent_schedule.json"
RUNS_FILE = DATA_DIR / "agent_schedule_runs.jsonl"
MIN_INTERVAL = 5


def _now() -> datetime:
    return datetime.now()


def load() -> list[dict]:
    """Все задачи расписания."""

    document = read_json_object(SCHEDULE_FILE)
    items = document.get("tasks")

    if not isinstance(items, list):
        return []

    return [item for item in items if isinstance(item, dict)]


def save(items: list[dict]) -> None:
    """Записывает расписание."""

    write_json(SCHEDULE_FILE, {"tasks": items})


def add(
    task: str,
    every_minutes: int = 60,
    max_steps: int = 6,
    policy: str = "read",
) -> dict:
    """Добавляет задачу в расписание."""

    text = str(task or "").strip()

    if not text:
        raise ValueError("Задача пустая.")

    if policy != "read":
        raise ValueError("Планировщик разрешает только policy=read.")

    interval = max(MIN_INTERVAL, int(every_minutes))
    entry = {
        "id": uuid.uuid4().hex[:8],
        "task": text[:1000],
        "every_minutes": interval,
        "max_steps": min(40, max(1, int(max_steps))),
        "policy": "read",
        "enabled": True,
        "last_run": "",
    }

    items = load()
    items.append(entry)
    save(items)

    return entry


def remove(task_id: str) -> bool:
    """Удаляет задачу по id."""

    items = load()
    kept = [item for item in items if item.get("id") != task_id]

    if len(kept) == len(items):
        return False

    save(kept)

    return True


def set_enabled(task_id: str, enabled: bool) -> bool:
    """Включает или выключает задачу."""

    items = load()
    found = False

    for item in items:
        if item.get("id") == task_id:
            item["enabled"] = bool(enabled)
            found = True

    if found:
        save(items)

    return found


def due(now: datetime | None = None) -> list[dict]:
    """Задачи, которые пора запускать."""

    moment = now or _now()
    result = []

    for item in load():
        if not item.get("enabled", True):
            continue

        last = str(item.get("last_run") or "")

        if last:
            try:
                previous = datetime.fromisoformat(last)
            except ValueError:
                previous = moment - timedelta(days=1)
        else:
            previous = moment - timedelta(days=1)

        interval = timedelta(
            minutes=max(MIN_INTERVAL, int(item.get("every_minutes") or 60))
        )

        if moment - previous >= interval:
            result.append(item)

    return result


def mark_run(task_id: str, now: datetime | None = None) -> None:
    """Отмечает время последнего запуска."""

    moment = (now or _now()).isoformat(timespec="seconds")
    items = load()

    for item in items:
        if item.get("id") == task_id:
            item["last_run"] = moment

    save(items)


def record_result(entry: dict) -> None:
    """Пишет итог фонового запуска в JSONL."""

    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": _now().isoformat(timespec="seconds"),
        **entry,
    }

    with RUNS_FILE.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(payload, ensure_ascii=False) + "\n"
        )
