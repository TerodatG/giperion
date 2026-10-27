# Giperion/tools/agent_queue.py                                       v001
# Очередь read-only задач агента: add/list/run/clear.
# Последнее изменение: первый вариант — поверх core.agent.queue.

import argparse
import sys

from config import BASE_DIR
from terminal.core.agent import queue as task_queue
from terminal.core.agent.loop import run_agent
from tools.eval_runner import build_brain


def _print_items(items: list[dict]) -> None:
    for item in items:
        print(
            f"{item.get('status'):8} · p{item.get('priority', 0)} · "
            f"{item.get('id')} · {str(item.get('task'))[:80]}"
        )

        if item.get("error"):
            print("  ошибка:", str(item["error"])[:200])


def _run(limit: int, model: str, provider: str, steps: int) -> int:
    brain, model_name = build_brain(model, provider)
    print("Модель:", model_name)
    done = 0

    while done < max(1, limit):
        item = task_queue.take()

        if item is None:
            break

        result = run_agent(
            str(item["task"]),
            brain,
            BASE_DIR,
            max_steps=steps,
            policy="read",
            approve=None,
            ground_first=True,
        )
        ok = not result.cancelled and not result.error
        task_queue.finish(
            str(item["id"]),
            ok,
            result.answer,
            result.error,
        )
        print(("OK" if ok else "ОШИБКА"), "·", item["task"][:80])
        done += 1

    return 0 if done else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Очередь read-only задач агента.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("task")
    add.add_argument("--priority", type=int, default=0)
    sub.add_parser("list")
    run = sub.add_parser("run")
    run.add_argument("--limit", type=int, default=1)
    run.add_argument("--steps", type=int, default=5)
    run.add_argument("--model", default="")
    run.add_argument("--provider", default="")
    clear = sub.add_parser("clear")
    clear.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.command == "add":
        try:
            item = task_queue.add(args.task, args.priority)
        except ValueError as error:
            print("Не добавлено:", error)

            return 1

        print("Добавлено:", item["id"])

        return 0

    if args.command == "list":
        items = task_queue.load()
        _print_items(items)
        print("Итого:", task_queue.summary(items))

        return 0

    if args.command == "clear":
        print("Удалено:", task_queue.clear(not args.all))

        return 0

    return _run(args.limit, args.model, args.provider, args.steps)


if __name__ == "__main__":
    sys.exit(main())
