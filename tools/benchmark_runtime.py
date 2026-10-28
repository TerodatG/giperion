# Giperion/tools/benchmark_runtime.py                                 v001
# Замер холодного старта и скорости роутера.
# Последнее изменение: первый вариант — p50/p95.

import argparse
import json
import statistics
import time

from config import DATA_DIR, LOGS_DIR
from kraper_model import neural_loader
from kraper_model.language.linear_intent import LinearIntentRouter

EVAL_FILE = DATA_DIR / "eval_set.json"
REPORT_FILE = LOGS_DIR / "runtime_report.txt"
DEFAULT_LIMIT = 200


def measure_router(
    router: LinearIntentRouter,
    texts: list[str],
) -> tuple[float, float, float]:
    """Возвращает p50, p95 и среднее время предсказания в мс."""

    samples = []

    for text in texts:
        started = time.perf_counter()
        router.predict(text)
        samples.append((time.perf_counter() - started) * 1000)

    samples.sort()
    p50 = statistics.median(samples)
    p95 = samples[min(len(samples) - 1, int(len(samples) * 0.95))]
    average = statistics.mean(samples)

    return p50, p95, average


def load_texts(limit: int) -> list[str]:
    """Берёт natural-фразы для замера."""

    phrases = json.loads(
        EVAL_FILE.read_text(encoding="utf-8")
    )["phrases"]
    texts = [
        item["text"]
        for item in phrases
        if item.get("source") == "natural"
    ]

    return texts[:limit] if limit > 0 else texts


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Разбирает ключи запуска."""

    parser = argparse.ArgumentParser(
        description="Замер рантайма роутера.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Печатает и сохраняет отчёт о скорости."""

    args = parse_args(argv)
    started = time.perf_counter()
    parts = neural_loader.load_components()
    cold_start = time.perf_counter() - started

    if parts is None or parts.get("router") is None:
        print("Роутер не загружен.")

        return 1

    p50, p95, average = measure_router(
        parts["router"],
        load_texts(args.limit),
    )
    report = "\n".join(
        [
            "=== Рантайм Giperion ===",
            f"Холодный старт: {cold_start:.2f} с",
            f"p50: {p50:.3f} мс",
            f"p95: {p95:.3f} мс",
            f"Среднее: {average:.3f} мс",
            f"Генератор: {'да' if parts.get('generator') else 'нет'}",
        ]
    )

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
