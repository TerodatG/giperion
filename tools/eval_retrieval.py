# Giperion/tools/eval_retrieval.py                                    v001
# Проверка смыслового поиска: на каких местах находятся ожидаемые файлы.
# Последнее изменение: первый вариант — hit@1/hit@k по набору запросов.

import argparse
import json
import sys

from config import BASE_DIR
from terminal.core.agent import semantic
from tools.retrieval_cases import CASES


def _paths(text: str) -> list[str]:
    """Пути из ответа find_relevant в порядке выдачи."""

    found = []

    for line in str(text or "").splitlines():
        if not line.startswith("- "):
            continue

        body = line[2:]
        path = body.split(":", 1)[0].strip()

        if path:
            found.append(path)

    return found


def evaluate(limit: int = 5) -> list[dict]:
    """Ранг ожидаемого файла для каждого запроса."""

    rows = []

    for query, expected in CASES:
        result = semantic.find_relevant(
            BASE_DIR,
            query,
            limit=limit,
        )
        paths = _paths(result.text)
        rank = 0

        for position, path in enumerate(paths, start=1):
            if path == expected:
                rank = position
                break

        rows.append(
            {
                "query": query,
                "expected": expected,
                "rank": rank,
                "paths": paths,
            }
        )

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Смысловой поиск: hit@1 и hit@k по набору запросов.",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--fail",
        action="store_true",
        help="вернуть код 2, если хотя бы один запрос промахнулся",
    )
    args = parser.parse_args()

    rows = evaluate(max(1, min(20, args.limit)))

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for row in rows:
            mark = f"#{row['rank']}" if row["rank"] else "мимо"

            print(f"{mark:>4} · {row['query']}")
            print(f"       ожидался: {row['expected']}")

            if not row["rank"]:
                print("       выдача: " + ", ".join(row["paths"][:5]))

    hit_one = sum(1 for row in rows if row["rank"] == 1)
    hit_k = sum(1 for row in rows if row["rank"])
    total = len(rows)

    print()
    print(
        f"hit@1: {hit_one}/{total}; "
        f"hit@{args.limit}: {hit_k}/{total}"
    )

    if args.fail and hit_k != total:
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
