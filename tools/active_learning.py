# Giperion/tools/active_learning.py                                  v001
# Цикл активного обучения: накопитель → разметка → переобучение.
# Последнее изменение: первый вариант — отчёт и явное применение.

import argparse
from collections import Counter

from kraper_model.training import build_dataset
from shared.storage.json_store import write_json
from terminal.memory.memory import get_unknown_messages
from tools.apply_unknown import main as apply_draft
from tools.eval_intent_model import main as evaluate_router
from tools.label_unknown import (
    LABELS_FILE,
    _build_engine,
    build_pattern_index,
    suggest_action,
)
from tools.train_linear_intent import main as train_router


def collect_suggestions() -> list[dict]:
    """Собирает подсказки по накопителю непонятых фраз."""

    messages = get_unknown_messages()
    pattern_index = build_pattern_index()
    engine = _build_engine()
    records = []

    for message in messages:
        text = message.get("text", "")

        if not isinstance(text, str) or not text.strip():
            continue

        action, tag, note = suggest_action(
            text,
            pattern_index,
            engine,
        )
        record = {
            "text": text,
            "action": action,
            "note": note,
        }

        if tag:
            record["tag"] = tag

        records.append(record)

    return records


def summarize(records: list[dict]) -> dict[str, int]:
    """Считает действия в черновике разметки."""

    counts = Counter(
        record.get("action", "skip") for record in records
    )

    return {
        "total": len(records),
        "add": counts.get("add", 0),
        "trash": counts.get("trash", 0),
        "skip": counts.get("skip", 0),
    }


def write_draft(records: list[dict]) -> None:
    """Пишет черновик разметки для apply_unknown."""

    write_json(
        LABELS_FILE,
        {
            "_meta": {
                "path": "data/unknown_labels.json",
                "description": (
                    "Черновик активного обучения. add — добавить "
                    "в intents, trash — убрать как мусор, skip — "
                    "оставить в накопителе."
                ),
            },
            "labels": records,
        },
        trailing_newline=True,
    )


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Разбирает ключи запуска."""

    parser = argparse.ArgumentParser(
        description="Цикл активного обучения по накопителю.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="применить черновик и переобучить роутер",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Показывает подсказки и при --apply замыкает цикл."""

    args = parse_args(argv)
    records = collect_suggestions()

    if not records:
        print("Непонятых фраз нет — цикл не нужен.")

        return 0

    summary = summarize(records)
    write_draft(records)

    print(
        f"Фраз: {summary['total']}, "
        f"add: {summary['add']}, "
        f"trash: {summary['trash']}, "
        f"skip: {summary['skip']}"
    )
    print(f"Черновик: {LABELS_FILE}")

    if not args.apply:
        print("Проверь черновик и запусти с --apply.")

        return 0

    apply_draft()
    build_dataset.main()

    if train_router([]) != 0:
        print("Роутер не сохранён — проверь метрики.")

        return 1

    return evaluate_router(["--router", "--fail"])


if __name__ == "__main__":
    raise SystemExit(main())
