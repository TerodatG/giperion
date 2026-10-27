# Giperion/tools/agent_dag.py                                         v001
# Граф задач: зависимости, уровни, пропуск потомков и слияние веток.
# Последнее изменение: первый вариант — validate/run и JSON-план.

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tools.agent_parallel import (
    build_brain,
    merge_branches,
    run_read,
    run_write,
)


def _collect(tasks: list[dict]) -> tuple[list[str], dict[str, list[str]]]:
    """Собирает id и зависимости, проверяя форму записей."""

    ids: list[str] = []
    depends: dict[str, list[str]] = {}

    for item in tasks:
        if not isinstance(item, dict):
            raise ValueError("Пункт плана должен быть объектом.")

        name = str(item.get("id") or "").strip()

        if not name:
            raise ValueError("У пункта нет id.")

        if name in depends:
            raise ValueError(f"Повтор id: {name}")

        ids.append(name)
        raw = item.get("depends") or []

        if not isinstance(raw, list):
            raise ValueError(f"depends у {name} должен быть массивом.")

        depends[name] = [str(value) for value in raw]

    for name, deps in depends.items():
        for dep in deps:
            if dep not in depends:
                raise ValueError(
                    f"{name} зависит от неизвестной задачи {dep}."
                )

    return ids, depends


def _topological(
    ids: list[str],
    depends: dict[str, list[str]],
) -> list[str]:
    """Топологический порядок; остаток означает цикл."""

    order: list[str] = []
    ready = [name for name in ids if not depends[name]]

    while ready:
        name = ready.pop(0)
        order.append(name)

        for other in ids:
            if name in depends[other]:
                depends[other].remove(name)

                if not depends[other] and other not in order:
                    ready.append(other)

    return order


def validate(tasks: list[dict]) -> list[str]:
    """Проверяет id/зависимости и возвращает топологический порядок."""

    if not isinstance(tasks, list) or not tasks:
        raise ValueError("План пуст.")

    ids, depends = _collect(tasks)
    order = _topological(ids, depends)

    if len(order) != len(ids):
        raise ValueError("В графе задач есть цикл.")

    return order


def run(
    tasks: list[dict],
    runner,
    workers: int = 2,
) -> list[dict]:
    """Выполняет задачи уровнями; потомки упавшей задачи пропускаются."""

    order = validate(tasks)
    items = {str(item["id"]): item for item in tasks}
    results: dict[str, dict] = {}
    pending = set(order)

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        while pending:
            level = [
                name
                for name in order
                if name in pending
                and all(
                    dep in results
                    for dep in items[name].get("depends") or []
                )
            ]

            if not level:
                raise ValueError("Не удалось построить уровень задач.")

            runnable = []

            for name in level:
                pending.remove(name)
                failed = [
                    dep
                    for dep in items[name].get("depends") or []
                    if not results[dep].get("ok")
                ]

                if failed:
                    results[name] = {
                        "id": name,
                        "task": items[name].get("task", ""),
                        "ok": False,
                        "skipped": True,
                        "error": "Не выполнена зависимость: "
                        + ", ".join(failed),
                        "answer": "",
                        "branch": "",
                        "folder": "",
                    }
                else:
                    runnable.append(name)

            futures = {
                pool.submit(runner, items[name]): name
                for name in runnable
            }

            for future, name in futures.items():
                try:
                    value = future.result()
                except Exception as error:  # noqa: BLE001 — в отчёт
                    value = {
                        "ok": False,
                        "error": f"{type(error).__name__}: {error}",
                    }

                value = dict(value)
                value["id"] = name
                value.setdefault("task", items[name].get("task", ""))
                value.setdefault("answer", "")
                value.setdefault("error", "")
                value.setdefault("branch", "")
                value.setdefault("folder", "")
                results[name] = value

    return [results[name] for name in order]


def _load_plan(path: str) -> list[dict]:
    """Читает и проверяет JSON-план."""

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = document.get("tasks") if isinstance(document, dict) else None
    validate(tasks)

    return tasks


def _print_results(results: list[dict]) -> None:
    """Печатает итог по каждой задаче."""

    for item in results:
        mark = "ПРОПУСК" if item.get("skipped") else (
            "OK" if item["ok"] else "ОШИБКА"
        )
        print()
        print(f"{mark} · {item['id']} · {item['task']}")

        if item["branch"]:
            print(f"ветка: {item['branch']}")

        print("ответ:", (item["answer"] or item["error"] or "—")[:400])


def _merge_results(results: list[dict]) -> None:
    """Сливает успешные ветки."""

    branches = [
        item["branch"]
        for item in results
        if item["ok"] and item["branch"]
    ]

    for branch, code, output in merge_branches(branches):
        mark = "OK" if code == 0 else "КОНФЛИКТ"
        print(f"{mark} · {branch}: {output[:300]}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Выполнить план задач с зависимостями.",
    )
    parser.add_argument("plan", help="JSON: {\"tasks\": [{id, task, depends}]}")
    parser.add_argument("--steps", type=int, default=6)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--policy", default="confirm")
    parser.add_argument("--merge", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--provider", default="")
    args = parser.parse_args()

    try:
        tasks = _load_plan(args.plan)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print("План не принят:", error)
        return 1

    brain, model_name = build_brain(args.model, args.provider)
    print("Модель:", model_name)
    print("Задач:", len(tasks), "· работников:", max(1, args.workers))

    def runner(item: dict) -> dict:
        write = bool(item.get("write") or args.write)

        if write:
            return run_write(
                str(item.get("task") or ""),
                brain,
                args.steps,
                str(item.get("policy") or args.policy),
            )

        return run_read(
            str(item.get("task") or ""),
            brain,
            args.steps,
        )

    results = run(tasks, runner, args.workers)
    _print_results(results)

    if args.merge:
        _merge_results(results)

    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
