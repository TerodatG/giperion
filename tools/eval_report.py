# Giperion/tools/eval_report.py                                       v001
# Сводка, история и отчёт стенда.
# Последнее изменение: вынесено из eval_agent.

import json
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

OUTPUT_DIR = DATA_DIR / "agent_eval"
LATEST = OUTPUT_DIR / "latest.json"



def _empty_summary() -> dict:
    """Пустая сводка для нулевого прогона."""

    return {
        "total": 0,
        "passed": 0,
        "success_rate": 0.0,
        "avg_steps": 0.0,
        "avg_duration_s": 0.0,
        "max_context": 0,
        "tokens": 0,
        "cost": 0.0,
        "runs": 0,
        "stable_tasks": 0,
        "flaky_tasks": 0,
        "task_ids": [],
        "per_task": {},
    }


def _group_results(
    results: list[dict],
) -> tuple[dict[str, list[dict]], dict[str, dict], int, int]:
    """Группирует результаты по задачам и считает стабильность."""

    groups: dict[str, list[dict]] = {}

    for number, item in enumerate(results):
        key = str(item.get("id") or f"#{number}")
        groups.setdefault(key, []).append(item)

    per_task = {}
    stable_tasks = 0
    flaky_tasks = 0

    for key, items in groups.items():
        ok_count = sum(1 for item in items if item["ok"])
        count = len(items)

        per_task[key] = {
            "attempts": count,
            "passed": ok_count,
            "avg_steps": round(
                sum(item["steps"] for item in items) / count,
                1,
            ),
            "avg_duration_s": round(
                sum(item["duration_s"] for item in items) / count,
                1,
            ),
            "tokens": sum(int(item.get("tokens") or 0) for item in items),
            "cost": round(
                sum(float(item.get("cost") or 0.0) for item in items),
                6,
            ),
        }

        if count > 1:
            if ok_count == count:
                stable_tasks += 1
            elif ok_count:
                flaky_tasks += 1

    return groups, per_task, stable_tasks, flaky_tasks


def summarize(results: list[dict]) -> dict:
    """Считает сводные метрики прогона и стабильность по задачам."""

    total = len(results)

    if not total:
        return _empty_summary()

    passed = sum(1 for item in results if item["ok"])
    groups, per_task, stable_tasks, flaky_tasks = _group_results(results)
    runs = max(int(item.get("attempt") or 1) for item in results)

    return {
        "total": total,
        "passed": passed,
        "success_rate": round(passed / total, 3),
        "avg_steps": round(
            sum(item["steps"] for item in results) / total,
            1,
        ),
        "avg_duration_s": round(
            sum(item["duration_s"] for item in results) / total,
            1,
        ),
        "max_context": max(item["context_chars"] for item in results),
        "tokens": sum(int(item.get("tokens") or 0) for item in results),
        "cost": round(
            sum(float(item.get("cost") or 0.0) for item in results),
            6,
        ),
        "runs": runs,
        "stable_tasks": stable_tasks,
        "flaky_tasks": flaky_tasks,
        "task_ids": sorted(groups),
        "per_task": per_task,
    }


def load_previous() -> dict:
    """Читает сводку прошлого прогона."""

    try:
        document = json.loads(LATEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    summary = document.get("summary")

    return summary if isinstance(summary, dict) else {}


HISTORY = OUTPUT_DIR / "history.jsonl"
BASELINE = OUTPUT_DIR / "baseline.json"


def append_history(model_name: str, summary: dict) -> None:
    """Добавляет строку в историю прогонов."""

    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": model_name,
        "passed": int(summary.get("passed") or 0),
        "total": int(summary.get("total") or 0),
        "success_rate": float(summary.get("success_rate") or 0.0),
        "avg_steps": float(summary.get("avg_steps") or 0.0),
        "avg_duration_s": float(summary.get("avg_duration_s") or 0.0),
        "runs": int(summary.get("runs") or 1),
        "stable_tasks": int(summary.get("stable_tasks") or 0),
        "flaky_tasks": int(summary.get("flaky_tasks") or 0),
    }

    try:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)

        with HISTORY.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )
    except OSError:
        pass


def read_history(limit: int = 10) -> list[dict]:
    """Последние записи истории прогонов."""

    try:
        lines = HISTORY.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    records = []

    for line in lines[-max(1, limit):]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(value, dict):
            records.append(value)

    return records


def save_baseline(model_name: str, summary: dict) -> Path:
    """Сохраняет стабильность задач как базовую линию."""

    per_task = {}

    for task_id, stats in (summary.get("per_task") or {}).items():
        attempts = int(stats.get("attempts") or 0)
        passed = int(stats.get("passed") or 0)
        per_task[str(task_id)] = {
            "attempts": attempts,
            "passed": passed,
            "rate": round(passed / attempts, 3) if attempts else 0.0,
        }

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model": model_name,
        "runs": int(summary.get("runs") or 1),
        "success_rate": float(summary.get("success_rate") or 0.0),
        "task_ids": list(summary.get("task_ids") or []),
        "per_task": per_task,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return BASELINE


def load_baseline() -> dict:
    """Читает сохранённую базовую линию, если она есть."""

    try:
        document = json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return document if isinstance(document, dict) else {}


def _same_task_set(old_ids, new_ids) -> bool:
    """Наборы задач совпадают (или сравнивать не с чем)."""

    if (
        not isinstance(old_ids, list)
        or not isinstance(new_ids, list)
        or not old_ids
        or not new_ids
    ):
        return True

    return sorted(old_ids) == sorted(new_ids)


def _rate_drop(baseline: dict, summary: dict) -> float:
    """Падение успеха в процентных пунктах."""

    old_rate = float(baseline.get("success_rate") or 0.0)
    new_rate = float(summary.get("success_rate") or 0.0)

    return (new_rate - old_rate) * 100


def _dropped_tasks(old_tasks, new_tasks) -> list[str]:
    """Задачи, которые были стабильны, а теперь почти всегда падают."""

    if not isinstance(old_tasks, dict) or not isinstance(new_tasks, dict):
        return []

    dropped = []

    for task_id, old in old_tasks.items():
        if not isinstance(old, dict):
            continue

        attempts = int(old.get("attempts") or 0)
        old_rate = float(old.get("rate") or 0.0)

        if attempts < 2 or old_rate < 0.67:
            continue

        new = new_tasks.get(task_id)

        if not isinstance(new, dict):
            continue

        new_attempts = int(new.get("attempts") or 0)
        new_passed = int(new.get("passed") or 0)

        if not new_attempts:
            continue

        if new_passed / new_attempts <= 0.34:
            dropped.append(
                f"{task_id}: было {int(old.get('passed') or 0)}/"
                f"{attempts}, стало {new_passed}/{new_attempts}"
            )

    return dropped


def baseline_note(
    baseline: dict,
    summary: dict,
    threshold: float = 10.0,
) -> str:
    """Сравнивает прогон с базовой линией: общий успех и просевшие задачи."""

    if not baseline or not summary.get("total"):
        return ""

    if not _same_task_set(
        baseline.get("task_ids"),
        summary.get("task_ids"),
    ):
        return ""

    lines = []
    delta = _rate_drop(baseline, summary)

    if delta < -abs(threshold):
        lines.append(
            f"РЕГРЕССИЯ: успех ниже базовой линии на {abs(delta):.0f} п.п. "
            f"(порог {abs(threshold):.0f})."
        )

    dropped = _dropped_tasks(
        baseline.get("per_task"),
        summary.get("per_task"),
    )

    if dropped:
        lines.append("Просели задачи: " + "; ".join(dropped))

    return "\n".join(lines)


def regression_note(
    previous: dict,
    summary: dict,
    threshold: float = 10.0,
) -> str:
    """Предупреждение, если успех упал сильнее порога."""

    if not previous or not summary.get("total"):
        return ""

    old_runs = int(previous.get("runs") or 1)
    new_runs = int(summary.get("runs") or 1)

    if old_runs != new_runs:
        return ""

    old_ids = previous.get("task_ids")
    new_ids = summary.get("task_ids")

    if (
        isinstance(old_ids, list)
        and isinstance(new_ids, list)
        and old_ids
        and new_ids
        and sorted(old_ids) != sorted(new_ids)
    ):
        return ""

    old_rate = float(previous.get("success_rate") or 0.0)
    new_rate = float(summary.get("success_rate") or 0.0)
    delta = (new_rate - old_rate) * 100

    if delta < -abs(threshold):
        return (
            f"РЕГРЕССИЯ: успех ниже прошлого на {abs(delta):.0f} п.п. "
            f"(порог {abs(threshold):.0f})."
        )

    return ""


def save_report(
    model_name: str,
    results: list[dict],
    summary: dict,
) -> Path:
    """Пишет отчёт с датой и обновляет latest.json."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    created = datetime.now()
    payload = {
        "created_at": created.isoformat(timespec="seconds"),
        "model": model_name,
        "tasks": results,
        "summary": summary,
    }

    path = OUTPUT_DIR / created.strftime("%Y%m%d-%H%M%S.json")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    LATEST.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return path
