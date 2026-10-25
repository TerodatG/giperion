# Giperion/terminal/core/agent/runs.py                               v002
# Журнал прогонов агента: шаги, время, подтверждения, итог.
# Последнее изменение: чтение всего журнала для показателей развития.

import json
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

RUNS_FILE = DATA_DIR / "agent_runs.jsonl"


def record_run(
    task: str,
    model: str,
    steps: int,
    approvals: int,
    duration_s: float,
    answer: str = "",
    error: str = "",
    cancelled: bool = False,
    tokens: int = 0,
    cost: float = 0.0,
    retries: int = 0,
    files: list[str] | None = None,
    started_at: str = "",
    root: str = "",
) -> None:
    """Добавляет одну строку в журнал; ошибки записи не ломают агента."""

    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "started_at": str(started_at)[:40],
        "root": str(root)[:500],
        "task": str(task)[:500],
        "model": str(model)[:120],
        "steps": int(steps),
        "approvals": int(approvals),
        "duration_s": round(float(duration_s), 2),
        "answer": str(answer)[:1000],
        "error": str(error)[:500],
        "cancelled": bool(cancelled),
        "tokens": int(tokens),
        "cost": round(float(cost), 6),
        "retries": int(retries),
        "files": [str(item)[:300] for item in (files or [])][:50],
    }

    try:
        RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)

        with Path(RUNS_FILE).open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )
    except OSError:
        pass


def read_runs(limit: int = 20) -> list[dict]:
    """Читает записи журнала; `limit` <= 0 — весь журнал."""

    if not Path(RUNS_FILE).exists():
        return []

    try:
        lines = Path(RUNS_FILE).read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError:
        return []

    selected = lines if limit <= 0 else lines[-max(1, limit):]
    records = []

    for line in selected:
        try:
            value = json.loads(line)

            if isinstance(value, dict):
                records.append(value)
        except json.JSONDecodeError:
            continue

    return records


def read_all_runs() -> list[dict]:
    """Читает весь журнал прогонов."""

    return read_runs(limit=0)
