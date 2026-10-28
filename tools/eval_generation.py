# Giperion/tools/eval_generation.py                                  v001
# Оценка генератора ответов: доля ответов и совпадение с намерением.
# Последнее изменение: первый вариант — покрытие и согласованность.

import argparse
import json

from config import DATA_DIR, LOGS_DIR
from kraper_model.neural_engine import (
    GENERATION_THRESHOLD,
    NeuralEngine,
)
from kraper_model.neural_loader import load_components

EVAL_FILE = DATA_DIR / "eval_set.json"
REPORT_FILE = LOGS_DIR / "generation_report.txt"

DEFAULT_LIMIT = 200
DEFAULT_MIN_CONSISTENCY = 0.85


def load_examples(limit: int) -> list[dict]:
    """Читает отложенный набор и ограничивает выборку."""

    document = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    phrases = document.get("phrases", [])

    return phrases if limit <= 0 else phrases[:limit]


def evaluate(
    engine: NeuralEngine,
    examples: list[dict],
) -> dict[str, float]:
    """Считает, как часто генератор отвечает и не уходит от темы."""

    candidates = 0
    generated = 0
    consistent = 0
    lengths = []

    for example in examples:
        _label, confidence = engine.classify(example["text"])

        if confidence < GENERATION_THRESHOLD:
            continue

        candidates += 1
        answer = engine.generate(example["text"])

        if not answer:
            continue

        generated += 1
        lengths.append(len(answer))

        if engine._matches_intent(
            answer,
            example["label"],
        ):
            consistent += 1

    return {
        "examples": float(len(examples)),
        "candidates": float(candidates),
        "generated": float(generated),
        "consistent": float(consistent),
        "generation_rate": (
            generated / candidates if candidates else 0.0
        ),
        "consistency": (
            consistent / generated if generated else 0.0
        ),
        "average_length": (
            sum(lengths) / len(lengths) if lengths else 0.0
        ),
    }


def build_report(metrics: dict[str, float]) -> str:
    """Собирает текстовый отчёт."""

    lines = [
        "=== Оценка генератора Giperion ===",
        f"Фраз в выборке: {int(metrics['examples'])}",
        (
            "Кандидатов на генерацию "
            f"(уверенность ≥ {GENERATION_THRESHOLD:.2f}): "
            f"{int(metrics['candidates'])}"
        ),
        f"Сгенерировано ответов: {int(metrics['generated'])}",
        f"Доля генерации: {metrics['generation_rate']:.3f}",
        f"Совпало с намерением: {metrics['consistency']:.3f}",
        f"Средняя длина: {metrics['average_length']:.1f} символов",
    ]

    return "\n".join(lines)


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Разбирает ключи запуска."""

    parser = argparse.ArgumentParser(
        description="Оценка генератора ответов.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="сколько фраз проверить (0 — все)",
    )
    parser.add_argument(
        "--fail",
        action="store_true",
        help="вернуть код 1 при низкой согласованности",
    )
    parser.add_argument(
        "--min-consistency",
        type=float,
        default=DEFAULT_MIN_CONSISTENCY,
        help="минимальная доля ответов по теме",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Проверяет генератор и пишет отчёт."""

    args = parse_args(argv)
    parts = load_components()

    if parts is None:
        print("Нейросеть не загружена — оценивать нечего.")

        return 1 if args.fail else 0

    engine = NeuralEngine(**parts)
    examples = load_examples(args.limit)

    if not examples:
        print("Отложенный набор пуст — нечего проверять.")

        return 1 if args.fail else 0

    metrics = evaluate(engine, examples)
    report = build_report(metrics)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")

    print(
        f"Кандидатов: {int(metrics['candidates'])}, "
        f"сгенерировано: {int(metrics['generated'])}, "
        f"согласованность: {metrics['consistency']:.3f}"
    )
    print(f"Отчёт: {REPORT_FILE}")

    if (
        args.fail
        and metrics["candidates"] > 0
        and metrics["consistency"] < args.min_consistency
    ):
        print(
            "Порог не пройден: "
            f"{metrics['consistency']:.3f} < "
            f"{args.min_consistency:.3f}"
        )

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
