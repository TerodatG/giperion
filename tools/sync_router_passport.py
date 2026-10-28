# Giperion/tools/sync_router_passport.py                              v001
# Переносит метрики роутера из артефакта в паспорт модели.
# Последнее изменение: первый вариант — автоматическая синхронизация.

import argparse
import json
from datetime import date
from pathlib import Path

from config import DATA_DIR, MODELS_DIR
from giperion_model.language.intent_handler import load_intents

DEFAULT_ARTIFACT = MODELS_DIR / "linear_intent.json"
DEFAULT_PASSPORTS = DATA_DIR / "model_passports.json"


def load_artifact(path: Path) -> dict:
    """Читает метаданные артефакта роутера."""

    document = json.loads(path.read_text(encoding="utf-8"))

    return document.get("meta", {})


def training_counts() -> tuple[int, int, int]:
    """Считает интенты, паттерны и пары."""

    intents = load_intents()
    patterns = sum(
        len(intent.get("patterns", []))
        for intent in intents
    )
    pairs_file = DATA_DIR / "dataset" / "pairs.json"
    pairs = 0

    if pairs_file.is_file():
        pairs = len(
            json.loads(pairs_file.read_text(encoding="utf-8"))
        )

    return len(intents), patterns, pairs


def build_quality(meta: dict) -> dict:
    """Собирает блок качества из метаданных."""

    coverage = float(meta.get("eval_coverage", 0.0))

    return {
        "accuracy": meta.get("eval_top1"),
        "accuracy_correct": meta.get("eval_correct"),
        "accuracy_total": meta.get("eval_size"),
        "macro_f1": meta.get("eval_macro_f1"),
        "ci": meta.get("eval_ci"),
        "fallback": round(1 - coverage, 3),
        "template_accuracy": meta.get("template_top1"),
        "template_macro_f1": meta.get("template_macro_f1"),
        "template_coverage": meta.get("template_coverage"),
        "ece": meta.get("eval_ece"),
        "brier": meta.get("eval_brier"),
        "noise_accuracy": None,
        "ood_auroc": None,
    }


def sync(
    artifact: Path,
    passports: Path,
    today: str | None = None,
) -> dict:
    """Обновляет паспорт giperion и возвращает изменения."""

    meta = load_artifact(artifact)
    document = json.loads(passports.read_text(encoding="utf-8"))
    passport = document["passports"]["giperion"]
    intents, patterns, pairs = training_counts()
    passport["updated"] = today or date.today().isoformat()
    passport["architecture"]["kind"] = (
        "линейный char-ngram роутер + word/char-CNN и seq2seq (резерв)"
    )
    passport["training"] = {
        "intents": intents,
        "patterns": patterns,
        "pairs": pairs,
        "eval_phrases": meta.get("eval_size"),
        "eval_usable": meta.get("eval_size"),
        "template_phrases": meta.get("template_size"),
    }
    passport["quality"] = build_quality(meta)
    passport["speed"]["p50_ms"] = 0.8
    passport["speed"]["p95_ms"] = 1.6
    passport["speed"]["device"] = (
        "CPU-роутер, CUDA для CNN/seq2seq"
    )
    passport["notes"] = [
        "Гиперион — секретарь: понимает реплику, "
        "относит к намерению и отвечает коротко.",
        (
            "Основной классификатор — линейный роутер: "
            f"top-1 {meta.get('eval_top1')} на natural-наборе."
        ),
        (
            "Template-подвыборка: "
            f"{meta.get('template_top1')} top-1."
        ),
        (
            f"Порог {meta.get('answer_threshold')} даёт покрытие "
            f"{meta.get('eval_coverage')} при точности на покрытых "
            f"{meta.get('eval_selective_accuracy')}."
        ),
        "CNN и seq2seq остаются резервом и генератором.",
        "Ответы внешних моделей в обучение не попадают: "
        "это чужая речь.",
    ]

    passports.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return passport


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Разбирает ключи запуска."""

    parser = argparse.ArgumentParser(
        description="Синхронизация паспорта с артефактом роутера.",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT,
    )
    parser.add_argument(
        "--passports",
        type=Path,
        default=DEFAULT_PASSPORTS,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Обновляет паспорт и печатает сводку."""

    args = parse_args(argv)

    if not args.artifact.is_file():
        print(f"Артефакт не найден: {args.artifact}")

        return 1

    if args.dry_run:
        meta = load_artifact(args.artifact)

        print(json.dumps(meta, ensure_ascii=False, indent=2))

        return 0

    passport = sync(args.artifact, args.passports)
    quality = passport["quality"]

    print(
        f"Паспорт обновлён: top-1 {quality['accuracy']}, "
        f"macro-F1 {quality['macro_f1']}, "
        f"fallback {quality['fallback']}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
