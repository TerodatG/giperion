# Giperion/tools/eval_agent.py                                        v002
# Стенд оценки агента: CLI поверх задач, прогона и отчёта.
# Последнее изменение: код разнесён по eval_tasks/runner/report.

import argparse

from config import BASE_DIR
from terminal.core.agent.worktrees import WorktreeError
from tools.eval_report import (
    LATEST,
    OUTPUT_DIR,
    append_history,
    load_previous,
    read_history,
    regression_note,
    save_report,
    summarize,
)
from tools.eval_runner import build_brain, is_fatal, run_task
from tools.eval_tasks import (
    TASKS,
    EvalTask,
    _mcp_prepare,
    _plan_inspect,
    _subagents_inspect,
    _web_prepare,
    answer_has,
    file_equals,
    file_has,
    readme_line_count,
    tests_passed,
)

__all__ = [
    "LATEST",
    "OUTPUT_DIR",
    "TASKS",
    "EvalTask",
    "_mcp_prepare",
    "_plan_inspect",
    "_subagents_inspect",
    "_web_prepare",
    "answer_has",
    "append_history",
    "build_brain",
    "file_equals",
    "file_has",
    "is_fatal",
    "load_previous",
    "read_history",
    "readme_line_count",
    "regression_note",
    "run_task",
    "save_report",
    "summarize",
    "tests_passed",
]


def _show_history() -> None:
    """Печатает последние прогоны стенда."""

    records = read_history(10)

    if not records:
        print("История пуста: прогонов ещё не было.")

        return

    print("=== История прогонов ===")

    for record in records:
        print(
            f"{record.get('created_at', '—')} · "
            f"{record.get('model', '—')} · "
            f"{record.get('passed', 0)}/{record.get('total', 0)} "
            f"({float(record.get('success_rate') or 0) * 100:.0f} %) · "
            f"{record.get('avg_steps', 0)} шагов · "
            f"{record.get('avg_duration_s', 0)} с"
            + (
                f" · стабильно {record['stable_tasks']}"
                if record.get("runs", 1) > 1
                else ""
            )
        )

    return



def _report(
    *,
    tasks,
    results: list[dict],
    summary: dict,
    path,
    previous: dict,
    args,
) -> None:
    """Печатает стабильность, итог и сравнение с прошлым прогоном."""

    attempts = max(1, int(args.repeat))
    if attempts > 1:
        print()
        print("=== Стабильность ===")

        for task in tasks:
            stats = summary["per_task"].get(task.id)

            if not stats:
                continue

            passed = stats["passed"]
            total = stats["attempts"]
            mark = (
                "стабильно"
                if passed == total
                else ("плавает" if passed else "падает")
            )

            print(
                f"  {task.id:24} {passed}/{total} · {mark} · "
                f"{stats['avg_duration_s']} с"
            )

    print()
    print("=== Итог ===")
    print(
        f"Успех: {summary['passed']}/{summary['total']} "
        f"({summary['success_rate'] * 100:.0f} %)"
    )
    print(
        f"Среднее: {summary['avg_steps']} шагов, "
        f"{summary['avg_duration_s']} с, "
        f"контекст до {summary['max_context']} символов"
    )

    if attempts > 1:
        print(
            f"Задачи: стабильных {summary['stable_tasks']}, "
            f"плавающих {summary['flaky_tasks']}"
        )

    if summary.get("tokens"):
        money = (
            f", ${summary['cost']:.4f}"
            if summary.get("cost")
            else ""
        )
        print(f"Расход: {summary['tokens']} токенов{money}")

    expected = len(tasks) * attempts

    if len(results) < expected:
        print(
            f"Прогон остановлен на {len(results)} из {expected} попыток: "
            "провайдер исчерпал лимит."
        )

    if previous:
        old_ids = previous.get("task_ids")
        new_ids = summary.get("task_ids")
        same_set = (
            not isinstance(old_ids, list)
            or not isinstance(new_ids, list)
            or not old_ids
            or not new_ids
            or sorted(old_ids) == sorted(new_ids)
        )

        if not same_set:
            print(
                "Прошлый прогон: другой набор задач — сравнение пропущено."
            )
        else:
            old_total = int(previous.get("total") or 0)
            old_passed = int(previous.get("passed") or 0)
            old_rate = float(previous.get("success_rate") or 0.0)
            delta_points = (
                summary["success_rate"] - old_rate
            ) * 100
            sign = "+" if delta_points >= 0 else ""

            print(
                "Прошлый прогон: "
                f"{old_passed}/{old_total} "
                f"({old_rate * 100:.0f} %) · "
                f"{sign}{delta_points:.0f} п.п."
            )

    note = regression_note(previous, summary, args.threshold)

    if note:
        print(note)

    print("Отчёт:", path)

    if note and args.fail_on_regression:
        raise SystemExit(2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Оценка агента на задачах проекта.",
    )
    parser.add_argument("--model", default="")
    parser.add_argument("--provider", default="")
    parser.add_argument("--only", default="")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="сколько раз прогнать набор задач (стабильность)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=10.0,
        help="порог регрессии в процентных пунктах",
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="вернуть код 2, если успех упал ниже порога",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="показать историю прогонов и выйти",
    )
    args = parser.parse_args()

    if args.history:
        _show_history()
        return

    tasks = [
        task for task in TASKS
        if (args.full or not task.slow)
        and (not args.only or task.id == args.only)
    ]

    if not tasks:
        raise SystemExit("Нет задач под такие фильтры.")

    attempts = max(1, int(args.repeat))
    brain, model_name = build_brain(args.model, args.provider)
    previous = load_previous()

    print("=== Оценка агента ===")
    print("Модель:", model_name)

    if attempts > 1:
        print(f"Повторов: {attempts}")

    print()

    results: list[dict] = []
    stopped = False

    for attempt in range(1, attempts + 1):
        if attempts > 1:
            print(f"--- прогон {attempt}/{attempts} ---")

        for index, task in enumerate(tasks, start=1):
            print(f"[{index}/{len(tasks)}] {task.title}…")

            current = task

            if args.max_steps:
                current = EvalTask(
                    id=task.id,
                    title=task.title,
                    task=task.task,
                    check=task.check,
                    setup=task.setup,
                    max_steps=args.max_steps,
                    slow=task.slow,
                    notes=task.notes,
                    inspect=task.inspect,
                    prepare=task.prepare,
                )

            try:
                result = run_task(current, brain, BASE_DIR)
            except WorktreeError as error:
                result = {
                    "id": task.id,
                    "title": task.title,
                    "ok": False,
                    "note": f"worktree: {error}",
                    "steps": 0,
                    "approvals": 0,
                    "duration_s": 0.0,
                    "context_chars": 0,
                    "tokens": 0,
                    "cost": 0.0,
                    "answer": "",
                    "error": str(error),
                }

            result["attempt"] = attempt
            results.append(result)

            mark = "OK" if result["ok"] else "FAIL"

            print(
                f"    {mark} · шагов {result['steps']} · "
                f"{result['duration_s']} с · {result['note']}"
            )

            if is_fatal(result.get("error", "")):
                print(
                    "    Стоп: провайдер исчерпал лимит или отклонил "
                    "ключ — остальные задачи не запускаю."
                )
                stopped = True

                break

        if stopped:
            break

    summary = summarize(results)
    path = save_report(model_name, results, summary)
    append_history(model_name, summary)

    _report(
        tasks=tasks,
        results=results,
        summary=summary,
        path=path,
        previous=previous,
        args=args,
    )


if __name__ == "__main__":
    main()
