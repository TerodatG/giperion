# Giperion/tools/profile_startup.py                                  v001
# Замер импорта ключевых модулей и бюджета запуска.
# Последнее изменение: первый вариант — последовательные импорты.

import argparse
import importlib
import json
import sys
import time

MODULES = (
    "PySide6.QtWidgets",
    "terminal.core.agent.loop",
    "terminal.core.model_catalog",
    "terminal.ui.agent.dialog",
    "kraper_model.neural_engine",
)


def measure(modules=MODULES) -> list[dict]:
    """Время импорта каждого модуля по очереди."""

    rows = []

    for name in modules:
        started = time.perf_counter()

        try:
            importlib.import_module(name)
            error = ""
        except Exception as exc:  # noqa: BLE001 — модуль может быть тяжёлым
            error = f"{type(exc).__name__}: {exc}"

        rows.append(
            {
                "module": name,
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "error": error,
            }
        )

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Замерить импорт ключевых модулей.",
    )
    parser.add_argument("--budget", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = measure()
    total = round(sum(row["ms"] for row in rows), 1)

    if args.json:
        print(json.dumps({"total_ms": total, "modules": rows}, indent=2))
    else:
        for row in rows:
            mark = " !" if row["error"] else ""

            print(f"{row['ms']:8.1f} мс  {row['module']}{mark}")

            if row["error"]:
                print("         ", row["error"])

        print(f"{total:8.1f} мс  всего")

    if args.budget and total > args.budget:
        print(f"Бюджет превышен: {total} > {args.budget} мс")

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
