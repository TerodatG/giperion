# Giperion/tools/train_linear_intent.py                              v002
# Обучение линейного роутера намерений и экспорт весов в JSON.
# Последнее изменение: C=30 и баланс классов.

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

from config import DATA_DIR, MODELS_DIR
from giperion_model.language.intent_handler import load_intents
from giperion_model.language.intent_topics import (
    INTENT_TOPICS,
    TOPIC_AUGMENT_TEMPLATES,
)
from giperion_model.language.linear_intent import (
    ROUTER_CONFIDENCE_THRESHOLD,
    LinearIntentRouter,
)
from giperion_model.training.build_dataset import CLASSIFICATION_FILE
from shared.text_tools import normalize_message

EVAL_FILE = DATA_DIR / "eval_set.json"
DEFAULT_OUTPUT = MODELS_DIR / "linear_intent.json"
NGRAM_RANGE = (3, 5)
DEFAULT_TOP_WEIGHTS = 400
DEFAULT_MIN_TOP1 = 0.75
DEFAULT_MIN_MACRO_F1 = 0.70


def load_training_data() -> tuple[list[str], list[str]]:
    """Читает примеры «текст → намерение» из датасета."""

    document = json.loads(
        CLASSIFICATION_FILE.read_text(encoding="utf-8")
    )

    texts = [
        item["text"]
        for item in document
        if isinstance(item.get("text"), str)
    ]
    labels = [
        item["label"]
        for item in document
        if isinstance(item.get("text"), str)
    ]

    return texts, labels


def augment_topics(
    texts: list[str],
    labels: list[str],
) -> tuple[list[str], list[str]]:
    """Добавляет тематические формулировки для устойчивости роутера."""

    augmented_texts = list(texts)
    augmented_labels = list(labels)

    for tag, topic in INTENT_TOPICS.items():
        for template in TOPIC_AUGMENT_TEMPLATES:
            augmented_texts.append(template.format(topic=topic))
            augmented_labels.append(tag)

    return augmented_texts, augmented_labels


def training_patterns() -> set[str]:
    """Собирает фразы, которые нельзя оценивать как отложенные."""

    patterns = set()

    for intent in load_intents():
        for pattern in intent.get("patterns", []):
            if isinstance(pattern, str):
                patterns.add(normalize_message(pattern))

    return patterns


def load_eval_data(
    known_labels: set[str],
    source: str = "natural",
) -> tuple[list[str], list[str], list[str]]:
    """Читает отложенный набор и отбрасывает утечки."""

    document = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    patterns = training_patterns()
    texts = []
    labels = []
    notes = []

    for item in document.get("phrases", []):
        text = str(item.get("text", "")).strip()
        label = item.get("label")

        if not text or label not in known_labels:
            notes.append(f"пропущена запись: {item}")

            continue

        if normalize_message(text) in patterns:
            notes.append(f"утечка в обучение: «{text}»")

            continue

        item_source = item.get("source", "natural")

        if source != "all" and item_source != source:
            continue

        texts.append(text)
        labels.append(label)

    return texts, labels, notes


def file_sha256(path: Path) -> str:
    """Считает хеш файла для метаданных артефакта."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


def measure_artifact(
    path: Path,
    texts: list[str],
    labels: list[str],
    threshold: float,
) -> tuple[float, float]:
    """Меряет покрытие и точность уже сохранённого артефакта."""

    router = LinearIntentRouter.load(path)

    if router is None:
        return 0.0, 0.0

    answered = 0
    correct = 0

    for text, expected in zip(texts, labels, strict=False):
        result = router.predict(text)

        if result is None:
            continue

        predicted, confidence = result

        if confidence < threshold:
            continue

        answered += 1
        correct += int(predicted == expected)

    coverage = answered / len(labels) if labels else 0.0
    accuracy = correct / answered if answered else 0.0

    return coverage, accuracy


def update_meta(path: Path, updates: dict) -> None:
    """Дописывает поля в meta готового артефакта."""

    document = json.loads(path.read_text(encoding="utf-8"))
    document["meta"].update(updates)
    path.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def fit_router(
    texts: list[str],
    labels: list[str],
    penalty_c: float,
) -> tuple[TfidfVectorizer, LogisticRegression]:
    """Обучает TF-IDF и логистическую регрессию."""

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=NGRAM_RANGE,
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(texts)
    model = LogisticRegression(
        max_iter=2000,
        C=penalty_c,
        class_weight="balanced",
    )
    model.fit(matrix, labels)

    return vectorizer, model


def evaluate(
    vectorizer: TfidfVectorizer,
    model: LogisticRegression,
    texts: list[str],
    labels: list[str],
) -> tuple[float, float]:
    """Считает top-1 и macro-F1 на отложенном наборе."""

    predictions = model.predict(vectorizer.transform(texts))
    correct = sum(
        1
        for expected, actual in zip(labels, predictions, strict=False)
        if expected == actual
    )
    accuracy = correct / len(labels) if labels else 0.0
    macro = f1_score(
        labels,
        predictions,
        average="macro",
        zero_division=0,
    )

    return accuracy, float(macro)


def coefficient_rows(
    model: LogisticRegression,
) -> tuple[list[np.ndarray], list[float]]:
    """Приводит бинарную модель к двум строкам весов."""

    if len(model.classes_) == 2 and model.coef_.shape[0] == 1:
        zeros = np.zeros_like(model.coef_[0])

        return (
            [zeros, model.coef_[0]],
            [0.0, float(model.intercept_[0])],
        )

    return (
        [row for row in model.coef_],
        [float(value) for value in model.intercept_],
    )


def compact_weights(
    model: LogisticRegression,
    limit: int,
) -> list[list[list[float]]]:
    """Оставляет самые весомые признаки каждого класса."""

    rows, _intercept = coefficient_rows(model)
    weights = []

    for row in rows:
        nonzero = np.flatnonzero(row)

        if limit > 0 and len(nonzero) > limit:
            order = np.argsort(np.abs(row[nonzero]))
            nonzero = nonzero[order[-limit:]]

        weights.append(
            [
                [int(index), round(float(row[index]), 6)]
                for index in nonzero
            ]
        )

    return weights


def export_router(
    vectorizer: TfidfVectorizer,
    model: LogisticRegression,
    output: Path,
    top_weights: int,
    meta: dict,
) -> None:
    """Пишет компактный JSON, пригодный для чистого Python."""

    pairs = sorted(
        vectorizer.vocabulary_.items(),
        key=lambda item: item[1],
    )
    _rows, intercept = coefficient_rows(model)
    document = {
        "meta": {
            "version": 1,
            "created": date.today().isoformat(),
            "classes": len(model.classes_),
            "ngram_range": list(NGRAM_RANGE),
            "top_weights": top_weights,
            **meta,
        },
        "labels": [str(label) for label in model.classes_],
        "vocabulary": [gram for gram, _index in pairs],
        "idf": [
            round(float(vectorizer.idf_[index]), 6)
            for _gram, index in pairs
        ],
        "intercept": [
            round(float(value), 6)
            for value in intercept
        ],
        "weights": compact_weights(model, top_weights),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Разбирает ключи запуска."""

    parser = argparse.ArgumentParser(
        description="Обучение линейного роутера намерений."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="куда сохранить JSON с весами",
    )
    parser.add_argument(
        "--top-weights",
        type=int,
        default=DEFAULT_TOP_WEIGHTS,
        help="сколько весов оставить каждому классу",
    )
    parser.add_argument(
        "--c",
        type=float,
        default=30.0,
        help="регуляризация логистической регрессии",
    )
    parser.add_argument(
        "--min-top1",
        type=float,
        default=DEFAULT_MIN_TOP1,
    )
    parser.add_argument(
        "--min-macro-f1",
        type=float,
        default=DEFAULT_MIN_MACRO_F1,
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Обучает роутер, проверяет качество и сохраняет веса."""

    args = parse_args(argv)
    texts, labels = load_training_data()
    texts, labels = augment_topics(texts, labels)
    eval_texts, eval_labels, notes = load_eval_data(
        set(labels),
        "natural",
    )
    template_texts, template_labels, template_notes = (
        load_eval_data(set(labels), "template")
    )
    vectorizer, model = fit_router(texts, labels, args.c)
    accuracy, macro = evaluate(
        vectorizer,
        model,
        eval_texts,
        eval_labels,
    )
    template_accuracy, template_macro = evaluate(
        vectorizer,
        model,
        template_texts,
        template_labels,
    )

    print(
        f"Обучено на {len(texts)} примерах, "
        f"проверено на {len(eval_texts)} natural."
    )
    print(
        f"natural: top-1 {accuracy:.3f}, macro-F1 {macro:.3f}"
    )
    print(
        f"template: top-1 {template_accuracy:.3f}, "
        f"macro-F1 {template_macro:.3f}"
    )

    for note in notes + template_notes:
        print(f"Замечание: {note}")

    failures = []

    if accuracy < args.min_top1:
        failures.append(
            f"top-1 {accuracy:.3f} < {args.min_top1:.3f}"
        )

    if macro < args.min_macro_f1:
        failures.append(
            f"macro-F1 {macro:.3f} < {args.min_macro_f1:.3f}"
        )

    if failures:
        print("Роутер не сохранён:")

        for failure in failures:
            print(f"- {failure}")

        return 1

    export_router(
        vectorizer,
        model,
        args.output,
        args.top_weights,
        {
            "train_size": len(texts),
            "eval_size": len(eval_texts),
            "eval_top1": round(accuracy, 4),
            "eval_macro_f1": round(macro, 4),
            "template_size": len(template_texts),
            "template_top1": round(template_accuracy, 4),
            "template_macro_f1": round(template_macro, 4),
            "answer_threshold": ROUTER_CONFIDENCE_THRESHOLD,
            "penalty_c": args.c,
            "class_weight": "balanced",
            "dataset_sha256": file_sha256(CLASSIFICATION_FILE),
            "eval_sha256": file_sha256(EVAL_FILE),
        },
    )

    coverage, selective = measure_artifact(
        args.output,
        eval_texts,
        eval_labels,
        ROUTER_CONFIDENCE_THRESHOLD,
    )
    template_coverage, template_selective = measure_artifact(
        args.output,
        template_texts,
        template_labels,
        ROUTER_CONFIDENCE_THRESHOLD,
    )
    update_meta(
        args.output,
        {
            "eval_coverage": round(coverage, 4),
            "eval_selective_accuracy": round(selective, 4),
            "template_coverage": round(template_coverage, 4),
            "template_selective_accuracy": round(
                template_selective,
                4,
            ),
        },
    )
    print(
        f"Покрытие natural: {coverage:.3f}, "
        f"точность: {selective:.3f}"
    )
    print(
        f"Покрытие template: {template_coverage:.3f}, "
        f"точность: {template_selective:.3f}"
    )

    size = args.output.stat().st_size / 1e6
    print(f"Веса: {args.output} ({size:.2f} МБ)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
