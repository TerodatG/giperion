# Giperion/tools/agent_parallel.py                                     v001
# Несколько задач агента параллельно: чтение или запись в worktrees.
# Последнее изменение: первый вариант — пул и отдельные ветки.

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import BASE_DIR
from terminal.core.agent.loop import run_agent
from terminal.core.agent.worktrees import create_worktree
from tools.eval_runner import build_brain

GIT = r"C:\Program Files\Git\cmd\git.exe"


def _git() -> str:
    return GIT if Path(GIT).is_file() else "git"


def merge_branches(branches: list[str]) -> list[tuple[str, int, str]]:
    """Сливает ветки в текущую; конфликт возвращает ошибку."""

    results = []
    git = _git()

    for branch in branches:
        try:
            done = subprocess.run(
                [git, "merge", "--no-ff", branch],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            output = (
                (done.stdout or "") + (done.stderr or "")
            ).strip()[-500:]
            results.append((branch, done.returncode, output))
        except (OSError, subprocess.TimeoutExpired) as error:
            results.append((branch, 1, str(error)))

    return results


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
    parser.add_argument(
        "--merge",
        action="store_true",
        help="слить успешные ветки в текущую (только с --write)",
    )
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

    if args.merge and args.write:
        branches = [
            item["branch"]
            for item in results
            if item["ok"] and item["branch"]
        ]

        if not branches:
            print("Нет успешных веток для слияния.")
        else:
            print()
            print("Слияние веток:")

            for branch, code, output in merge_branches(branches):
                mark = "OK" if code == 0 else "КОНФЛИКТ"
                print(f"{mark} · {branch}: {output[:300]}")

    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
