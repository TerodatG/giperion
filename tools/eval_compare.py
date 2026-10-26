# Giperion/tools/eval_compare.py                                     v001
# Сравнение моделей по истории стенда: успех, шаги, время.
# Последнее изменение: первый вариант — сводка по model за N прогонов.

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from config import DATA_DIR

HISTORY = DATA_DIR / "agent_eval" / "history.jsonl"


def _rows(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    result = []

    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(item, dict):
            result.append(item)

    return result


def compare(path: Path = HISTORY, last: int = 5) -> list[dict]:
    """Средние показатели по каждой модели за последние N прогонов."""

    groups: dict[str, list[dict]] = defaultdict(list)

    for item in _rows(path):
        groups[str(item.get("model") or "unknown")].append(item)

    result = []

    for model, items in groups.items():
        recent = items[-max(1, int(last)):]
        count = len(recent)
        result.append(
            {
                "model": model,
                "runs": count,
                "success": round(
                    sum(float(x.get("success_rate") or 0) for x in recent)
                    / count,
                    3,
                ),
                "steps": round(
                    sum(float(x.get("avg_steps") or 0) for x in recent)
                    / count,
                    1,
                ),
                "seconds": round(
                    sum(
                        float(x.get("avg_duration_s") or 0)
                        for x in recent
                    )
                    / count,
                    1,
                ),
                "stable": round(
                    sum(int(x.get("stable_tasks") or 0) for x in recent)
                    / count,
                    1,
                ),
                "flaky": round(
                    sum(int(x.get("flaky_tasks") or 0) for x in recent)
                    / count,
                    1,
                ),
            }
        )

    return sorted(result, key=lambda row: -row["success"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Сравнить модели по истории прогонов стенда.",
    )
    parser.add_argument("--last", type=int, default=5)
    parser.add_argument("--history", default=str(HISTORY))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    rows = compare(Path(args.history), args.last)

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif not rows:
        print("История пуста: запустите стенд.")
    else:
        print(
            f"{'модель':32} {'успех':>7} {'шаги':>6} "
            f"{'сек':>6} {'стаб':>6} {'плавает':>8}"
        )

        for row in rows:
            print(
                f"{row['model'][:32]:32} "
                f"{row['success'] * 100:6.0f}% "
                f"{row['steps']:6.1f} {row['seconds']:6.1f} "
                f"{row['stable']:6.1f} {row['flaky']:8.1f}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
