# Giperion/terminal/core/agent/tasks.py                              v001
# Состояние задач агента: сохранение, список и восстановление истории.
# Последнее изменение: первый вариант — JSON на задачу и resume.

import json
import uuid
from datetime import datetime
from pathlib import Path

from config import DATA_DIR
from shared.storage.json_store import read_json_object, write_json
from terminal.core.agent.protocol import (
    AgentStep,
    ToolCall,
    ToolResult,
)

TASKS_DIR = DATA_DIR / "agent_tasks"

STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"
STATUS_CANCELLED = "cancelled"


def new_task_id() -> str:
    """Короткий уникальный идентификатор задачи."""

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:6]

    return f"{stamp}-{suffix}"


def task_file(task_id: str) -> Path:
    """Путь к файлу состояния."""

    return TASKS_DIR / f"{task_id}.json"


def serialize_history(
    history: list[tuple[ToolCall, ToolResult]],
) -> list[dict]:
    """История шагов в виде, пригодном для JSON."""

    return [
        {
            "tool": call.tool,
            "args": dict(call.args),
            "ok": bool(result.ok),
            "text": str(result.text)[:20000],
        }
        for call, result in history
    ]


def deserialize_history(data: object) -> list[tuple[ToolCall, ToolResult]]:
    """Восстанавливает историю из JSON."""

    if not isinstance(data, list):
        return []

    history = []

    for item in data:
        if not isinstance(item, dict):
            continue

        tool = item.get("tool")
        args = item.get("args") or {}

        if not isinstance(tool, str) or not tool.strip():
            continue

        if not isinstance(args, dict):
            args = {}

        history.append(
            (
                ToolCall(tool=tool.strip(), args=args),
                ToolResult(
                    bool(item.get("ok")),
                    str(item.get("text") or ""),
                ),
            )
        )

    return history


def serialize_steps(steps: list[AgentStep]) -> list[dict]:
    """Шаги трейса для JSON."""

    return [
        {
            "index": step.index,
            "kind": step.kind,
            "title": step.title,
            "detail": step.detail[:4000],
        }
        for step in steps
    ]


def deserialize_steps(data: object) -> list[AgentStep]:
    """Восстанавливает шаги трейса."""

    if not isinstance(data, list):
        return []

    steps = []

    for item in data:
        if not isinstance(item, dict):
            continue

        try:
            index = int(item.get("index", 0))
        except (TypeError, ValueError):
            index = 0

        steps.append(
            AgentStep(
                index=index,
                kind=str(item.get("kind") or "tool"),
                title=str(item.get("title") or ""),
                detail=str(item.get("detail") or ""),
            )
        )

    return steps


def save_state(state: dict) -> None:
    """Записывает состояние задачи на диск."""

    task_id = str(state.get("id") or "").strip()

    if not task_id:
        return

    TASKS_DIR.mkdir(parents=True, exist_ok=True)

    document = dict(state)
    document["updated_at"] = datetime.now().isoformat(
        timespec="seconds"
    )

    write_json(task_file(task_id), document)


def load_state(task_id: str) -> dict | None:
    """Читает состояние по идентификатору."""

    document = read_json_object(task_file(task_id))

    return document if document.get("id") else None


def list_states(limit: int = 50) -> list[dict]:
    """Список задач, сначала незавершённые и свежие."""

    if not TASKS_DIR.is_dir():
        return []

    states = []

    for path in TASKS_DIR.glob("*.json"):
        try:
            document = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            continue

        if isinstance(document, dict) and document.get("id"):
            states.append(document)

    states.sort(
        key=lambda item: str(item.get("updated_at", "")),
        reverse=True,
    )
    states.sort(
        key=lambda item: item.get("status") != STATUS_RUNNING,
    )

    return states[: max(1, limit)]


def remove_state(task_id: str) -> None:
    """Удаляет файл состояния."""

    try:
        task_file(task_id).unlink()
    except OSError:
        pass
