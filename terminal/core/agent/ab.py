# Giperion/terminal/core/agent/ab.py                                   v001
# A/B-прогон одной задачи на двух мозгах: успех, шаги, токены.
# Последнее изменение: первый вариант — compare/summarize.

from pathlib import Path

from terminal.core.agent.loop import run_agent


def summarize(result) -> dict:
    """Короткая сводка результата для сравнения."""

    return {
        "ok": not result.cancelled and not result.error,
        "answer": result.answer,
        "error": result.error,
        "steps": len(result.steps),
        "tokens": sum(
            int(item.get("tokens") or 0)
            for item in getattr(result, "usage", []) or []
        ),
        "cost": round(
            sum(
                float(item.get("cost") or 0.0)
                for item in getattr(result, "usage", []) or []
            ),
            6,
        ),
    }


def compare(
    task: str,
    brain_a,
    brain_b,
    root: Path,
    max_steps: int = 5,
    policy: str = "read",
) -> dict:
    """Выполняет одну задачу двумя мозгами и возвращает обе сводки."""

    first = run_agent(
        task,
        brain_a,
        Path(root),
        max_steps=max_steps,
        policy=policy,
        approve=None,
        ground_first=True,
    )
    second = run_agent(
        task,
        brain_b,
        Path(root),
        max_steps=max_steps,
        policy=policy,
        approve=None,
        ground_first=True,
    )

    return {
        "task": task,
        "a": summarize(first),
        "b": summarize(second),
    }
