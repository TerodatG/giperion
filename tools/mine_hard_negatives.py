# Giperion/tools/mine_hard_negatives.py                              v001
# Поиск сложных пар намерений по out-of-fold ошибкам роутера.
# Последнее изменение: первый вариант — confusion-отчёт для разметки.

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline

from config import LOGS_DIR
from kraper_model.language.intent_taxonomy import TAXONOMY_NOTES
from tools.train_linear_intent import (
    augment_topics,
    load_training_data,
)

DEFAULT_FOLDS = 5
DEFAULT_TOP = 15
DEFAULT_EXAMPLES = 3
REPORT_FILE = LOGS_DIR / "hard_negatives.json"


def rank_confusions(
    pairs: list[tuple[str, str]],
) -> list[tuple[tuple[str, str], int]]:
    """Сортирует пары «верно → предсказано» по частоте."""

    counts = Counter(pairs)

    return sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    )


def build_pipeline() -> Pipeline:
    """Собирает ту же модель, что и боевой роутер."""

    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    C=30,
                    class_weight="balanced",
                ),
            ),
        ]
    )


def collect_errors(
    texts: list[str],
    labels: list[str],
    folds: int,
) -> tuple[list[dict], list[tuple[str, str]]]:
    """Считает out-of-fold ошибки и возвращает пары путаниц."""

    pipeline = build_pipeline()
    splitter = StratifiedKFold(
        n_splits=folds,
        shuffle=True,
        random_state=42,
    )
    probabilities = cross_val_predict(
        pipeline,
        texts,
        labels,
        cv=splitter,
        method="predict_proba",
    )
    classes = np.array(sorted(set(labels)))
    predicted = classes[probabilities.argmax(axis=1)]
    confidence = probabilities.max(axis=1)
    errors = []
    pairs = []

    for text, truth, guess, score in zip(
        texts,
        labels,
        predicted,
        confidence,
        strict=False,
    ):
        if truth == guess:
            continue

        errors.append(
            {
                "text": text,
                "true": truth,
                "predicted": guess,
                "confidence": round(float(score), 3),
            }
        )
        pairs.append((truth, guess))

    return errors, pairs


def build_report(
    errors: list[dict],
    pairs: list[tuple[str, str]],
    top: int,
    examples: int,
) -> dict:
    """Собирает JSON-отчёт по частым путаницам."""

    ranked = rank_confusions(pairs)[:top]
    groups = []

    for (truth, guess), count in ranked:
        group = [
            error
            for error in errors
            if error["true"] == truth
            and error["predicted"] == guess
        ][:examples]

        groups.append(
            {
                "true": truth,
                "predicted": guess,
                "count": count,
                "note": TAXONOMY_NOTES.get((truth, guess), ""),
                "examples": group,
            }
        )

    return {
        "errors": len(errors),
        "pairs": len(ranked),
        "confusions": groups,
    }


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Разбирает ключи запуска."""

    parser = argparse.ArgumentParser(
        description="Поиск сложных пар намерений по OOF-ошибкам.",
    )
    parser.add_argument(
        "--folds",
        type=int,
        default=DEFAULT_FOLDS,
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
    )
    parser.add_argument(
        "--examples",
        type=int,
        default=DEFAULT_EXAMPLES,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPORT_FILE,
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Считает OOF-ошибки и пишет отчёт."""

    args = parse_args(argv)
    texts, labels = load_training_data()
    texts, labels = augment_topics(texts, labels)
    errors, pairs = collect_errors(
        texts,
        labels,
        args.folds,
    )
    report = build_report(
        errors,
        pairs,
        args.top,
        args.examples,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Ошибок: {report['errors']}, "
        f"пар: {report['pairs']}"
    )

    for group in report["confusions"]:
        print(
            f"{group['true']} → {group['predicted']}: "
            f"{group['count']}"
        )

        if group["note"]:
            print(f"    {group['note']}")

    print(f"Отчёт: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
