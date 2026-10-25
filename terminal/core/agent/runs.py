# Giperion/terminal/core/agent/runs.py                               v001
# Журнал прогонов агента: шаги, время, подтверждения, итог.
# Последнее изменение: первый вариант — JSONL в data/.

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
) -> None:
    """Добавляет одну строку в журнал; ошибки записи не ломают агента."""

    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "task": str(task)[:500],
        "model": str(model)[:120],
        "steps": int(steps),
        "approvals": int(approvals),
        "duration_s": round(float(duration_s), 2),
        "answer": str(answer)[:1000],
        "error": str(error)[:500],
        "cancelled": bool(cancelled),
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
    """Читает последние записи журнала."""

    if not Path(RUNS_FILE).exists():
        return []

    try:
        lines = Path(RUNS_FILE).read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError:
        return []

    records = []

    for line in lines[-max(1, limit):]:
        try:
            value = json.loads(line)

            if isinstance(value, dict):
                records.append(value)
        except json.JSONDecodeError:
            continue

    return records
