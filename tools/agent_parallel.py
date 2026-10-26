# Giperion/tools/agent_parallel.py                                     v001
# Несколько задач агента параллельно: чтение или запись в worktrees.
# Последнее изменение: первый вариант — пул и отдельные ветки.

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from config import BASE_DIR
from terminal.core.agent.loop import run_agent
from terminal.core.agent.worktrees import create_worktree
from tools.eval_runner import build_brain


def _fork(brain):
    """Копия мозга для параллельной задачи, если поддерживается."""

    fork = getattr(brain, "fork", None)

    return fork() if callable(fork) else brain


def run_read(task: str, brain, steps: int) -> dict:
    """Читающая задача в основном дереве."""

    result = run_agent(
        task,
        _fork(brain),
        BASE_DIR,
        max_steps=steps,
        policy="read",
        approve=None,
        ground_first=True,
    )

    return {
        "task": task,
        "ok": not result.cancelled and not result.error,
        "answer": result.answer,
        "error": result.error,
        "branch": "",
        "folder": "",
    }


def run_write(task: str, brain, steps: int, policy: str) -> dict:
    """Пишущая задача в отдельном worktree; слияние — вручную."""

    name = f"parallel-{int(time.time())}"
    folder, branch = create_worktree(BASE_DIR, name)
    result = run_agent(
        task,
        _fork(brain),
        folder,
        max_steps=steps,
        policy=policy,
        approve=lambda request: True,
        ground_first=True,
    )

    return {
        "task": task,
        "ok": not result.cancelled and not result.error,
        "answer": result.answer,
        "error": result.error,
        "branch": branch,
        "folder": str(folder),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Запустить несколько задач агента параллельно. Без --write "
            "только чтение; с --write каждая задача идёт в своём worktree "
            "и подтверждения одобряются автоматически."
        ),
    )
    parser.add_argument("tasks", nargs="+")
    parser.add_argument("--steps", type=int, default=6)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--policy", default="confirm")
    parser.add_argument("--model", default="")
    parser.add_argument("--provider", default="")
    args = parser.parse_args()

    if len(args.tasks) > 4:
        print("Не больше четырёх задач за раз.")
        return 1

    brain, model_name = build_brain(args.model, args.provider)

    print("Модель:", model_name)
    print("Режим:", "запись в worktrees" if args.write else "чтение")

    runner = (
        (lambda task: run_write(task, brain, args.steps, args.policy))
        if args.write
        else (lambda task: run_read(task, brain, args.steps))
    )

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(runner, args.tasks))

    for item in results:
        mark = "OK" if item["ok"] else "ОШИБКА"
        print()
        print(f"{mark} · {item['task']}")

        if item["branch"]:
            print(f"ветка: {item['branch']}")
            print(f"папка: {item['folder']}")

        print("ответ:", (item["answer"] or item["error"] or "—")[:400])

    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
