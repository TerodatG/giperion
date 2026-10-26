# Giperion/tools/agent_schedule.py                                     v001
# Расписание read-only задач агента: add/list/remove/run-due.
# Последнее изменение: первый вариант — JSON-расписание и запуск.

import argparse
import sys

from config import BASE_DIR
from terminal.core import schedule
from terminal.core.agent.loop import run_agent
from tools.eval_runner import build_brain


def _cmd_add(args) -> int:
    try:
        entry = schedule.add(
            args.task,
            every_minutes=args.every,
            max_steps=args.steps,
        )
    except ValueError as error:
        print("Не добавлено:", error)
        return 1

    print("Добавлено:", entry["id"], "·", entry["task"])
    return 0


def _cmd_list(_args) -> int:
    items = schedule.load()

    if not items:
        print("Расписание пустое.")
        return 0

    for item in items:
        state = "вкл" if item.get("enabled", True) else "выкл"
        print(
            f"{item.get('id')} · {state} · "
            f"каждые {item.get('every_minutes')} мин · "
            f"шагов {item.get('max_steps')} · {item.get('task')}"
        )

    return 0


def _cmd_remove(args) -> int:
    return 0 if schedule.remove(args.id) else 1


def _cmd_toggle(args) -> int:
    return 0 if schedule.set_enabled(args.id, args.enabled) else 1


def _cmd_due(_args) -> int:
    items = schedule.due()

    if not items:
        print("Нет задач к запуску.")
        return 0

    for item in items:
        print(f"пора: {item.get('id')} · {item.get('task')}")

    return 0


def _cmd_run(args) -> int:
    items = schedule.due()

    if not items:
        print("Нет задач к запуску.")
        return 0

    brain, model_name = build_brain(args.model, args.provider)
    print("Модель:", model_name)

    for item in items[:max(1, args.limit)]:
        print()
        print("Запуск:", item.get("task"))
        result = run_agent(
            str(item.get("task") or ""),
            brain,
            BASE_DIR,
            max_steps=int(item.get("max_steps") or 6),
            policy="read",
            approve=None,
            ground_first=True,
        )
        schedule.mark_run(str(item.get("id")))
        schedule.record_result(
            {
                "id": item.get("id"),
                "task": item.get("task"),
                "ok": not result.cancelled and not result.error,
                "steps": len(result.steps),
                "answer": (result.answer or "")[:1000],
                "error": result.error,
            }
        )
        print("Готово:", (result.answer or result.error or "нет ответа")[:300])

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Фоновые read-only задачи. Сами не запускаются: добавьте "
            "tools/agent_schedule.py run-due в Планировщик Windows."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add")
    add.add_argument("task")
    add.add_argument("--every", type=int, default=60)
    add.add_argument("--steps", type=int, default=6)
    add.set_defaults(handler=_cmd_add)

    listing = sub.add_parser("list")
    listing.set_defaults(handler=_cmd_list)

    remove = sub.add_parser("remove")
    remove.add_argument("id")
    remove.set_defaults(handler=_cmd_remove)

    enable = sub.add_parser("enable")
    enable.add_argument("id")
    enable.set_defaults(handler=_cmd_toggle, enabled=True)

    disable = sub.add_parser("disable")
    disable.add_argument("id")
    disable.set_defaults(handler=_cmd_toggle, enabled=False)

    due = sub.add_parser("run-due")
    due.add_argument("--limit", type=int, default=3)
    due.add_argument("--model", default="")
    due.add_argument("--provider", default="")
    due.set_defaults(handler=_cmd_run)

    due_only = sub.add_parser("due")
    due_only.set_defaults(handler=_cmd_due)

    args = parser.parse_args()

    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
