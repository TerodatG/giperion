# Giperion/tools/train_linear_intent.py                              v003
# Обучение линейного роутера намерений и экспорт весов в JSON.
# Последнее изменение: тематическая аугментация и bootstrap-метрики.

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline

from config import DATA_DIR, MODELS_DIR
from kraper_model.language.intent_handler import load_intents
from kraper_model.language.intent_topics import (
    INTENT_TOPICS,
    TOPIC_AUGMENT_TEMPLATES,
)
from kraper_model.language.linear_intent import (
    ROUTER_CONFIDENCE_THRESHOLD,
)
from kraper_model.training.build_dataset import CLASSIFICATION_FILE
from shared.text_tools import normalize_message
from tools.intent_metrics import (
    bootstrap_metrics,
    calibration_metrics,
)
from tools.router_artifact import (
    export_router,
    file_sha256,
    measure_artifact,
    update_meta,
)

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
) -> tuple[float, float, int]:
    """Считает top-1, macro-F1 и число верных ответов."""

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

    return accuracy, float(macro), correct


def calibration_scores(
    model: LogisticRegression,
    matrix,
    labels: list[str],
    temperature: float,
) -> tuple[float, float]:
    """Считает ECE и Brier для калиброванных вероятностей."""

    scores = np.asarray(model.decision_function(matrix))
    scaled = scores / temperature
    scaled -= scaled.max(axis=1, keepdims=True)
    exponents = np.exp(scaled)
    probabilities = exponents / exponents.sum(
        axis=1,
        keepdims=True,
    )
    confidence = probabilities.max(axis=1)
    predicted = model.classes_[probabilities.argmax(axis=1)]
    correct = [
        str(expected) == str(actual)
        for expected, actual in zip(
            labels,
            predicted,
            strict=False,
        )
    ]

    return calibration_metrics(
        confidence.tolist(),
        correct,
    )


def fit_temperature(
    texts: list[str],
    labels: list[str],
    penalty_c: float,
) -> float:
    """Подбирает температуру по OOF-вероятностям."""

    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=NGRAM_RANGE,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    C=penalty_c,
                    class_weight="balanced",
                ),
            ),
        ]
    )
    probabilities = cross_val_predict(
        pipeline,
        texts,
        labels,
        cv=StratifiedKFold(
            n_splits=5,
            shuffle=True,
            random_state=42,
        ),
        method="predict_proba",
    )
    classes = sorted(set(labels))
    truth = np.array(
        [classes.index(label) for label in labels]
    )
    scores = np.log(probabilities + 1e-12)
    rows = np.arange(len(truth))
    best_temperature = 1.0
    best_nll = float("inf")

    for temperature in np.arange(0.5, 3.01, 0.05):
        scaled = scores / temperature
        scaled -= scaled.max(axis=1, keepdims=True)
        exponents = np.exp(scaled)
        normalized = exponents / exponents.sum(
            axis=1,
            keepdims=True,
        )
        nll = -np.log(
            normalized[rows, truth] + 1e-12
        ).mean()

        if nll < best_nll:
            best_nll = float(nll)
            best_temperature = float(temperature)

    return best_temperature


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


def prepare_training(args: argparse.Namespace) -> dict:
    """Готовит данные и обучает модель."""

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
    temperature = fit_temperature(texts, labels, args.c)
    accuracy, macro, correct = evaluate(
        vectorizer,
        model,
        eval_texts,
        eval_labels,
    )
    template_accuracy, template_macro, template_correct = (
        evaluate(
            vectorizer,
            model,
            template_texts,
            template_labels,
        )
    )
    eval_predictions = model.predict(
        vectorizer.transform(eval_texts)
    )
    interval = bootstrap_metrics(
        eval_labels,
        list(eval_predictions),
        iterations=300,
    )
    eval_ci = (interval["top1_high"] - interval["top1_low"]) / 2
    ece, brier = calibration_scores(
        model,
        vectorizer.transform(eval_texts),
        eval_labels,
        temperature,
    )

    return {
        "texts": texts,
        "labels": labels,
        "eval_texts": eval_texts,
        "eval_labels": eval_labels,
        "notes": notes,
        "template_texts": template_texts,
        "template_labels": template_labels,
        "template_notes": template_notes,
        "vectorizer": vectorizer,
        "model": model,
        "temperature": temperature,
        "accuracy": accuracy,
        "macro": macro,
        "correct": correct,
        "template_accuracy": template_accuracy,
        "template_macro": template_macro,
        "template_correct": template_correct,
        "eval_ci": eval_ci,
        "ece": ece,
        "brier": brier,
    }


def finish_training(
    args: argparse.Namespace,
    data: dict,
) -> int:
    """Проверяет качество, сохраняет артефакт и печатает итог."""

    texts = data["texts"]
    eval_texts = data["eval_texts"]
    eval_labels = data["eval_labels"]
    notes = data["notes"]
    template_texts = data["template_texts"]
    template_labels = data["template_labels"]
    template_notes = data["template_notes"]
    vectorizer = data["vectorizer"]
    model = data["model"]
    temperature = data["temperature"]
    accuracy = data["accuracy"]
    macro = data["macro"]
    correct = data["correct"]
    template_accuracy = data["template_accuracy"]
    template_macro = data["template_macro"]
    template_correct = data["template_correct"]
    eval_ci = data["eval_ci"]
    ece = data["ece"]
    brier = data["brier"]

    print(
        f"Обучено на {len(texts)} примерах, "
        f"проверено на {len(eval_texts)} natural."
    )
    print(
        f"natural: top-1 {accuracy:.3f}, macro-F1 {macro:.3f}"
    )
    print(f"Температура: {temperature:.2f}")
    print(f"ECE: {ece:.3f}, Brier: {brier:.3f}")
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
            "eval_correct": correct,
            "eval_ci": round(eval_ci, 4),
            "eval_ece": round(ece, 4),
            "eval_brier": round(brier, 4),
            "template_size": len(template_texts),
            "template_top1": round(template_accuracy, 4),
            "template_macro_f1": round(template_macro, 4),
            "template_correct": template_correct,
            "answer_threshold": ROUTER_CONFIDENCE_THRESHOLD,
            "penalty_c": args.c,
            "class_weight": "balanced",
            "dataset_sha256": file_sha256(CLASSIFICATION_FILE),
            "eval_sha256": file_sha256(EVAL_FILE),
        },
        temperature,
    )

    natural = measure_artifact(
        args.output,
        eval_texts,
        eval_labels,
        ROUTER_CONFIDENCE_THRESHOLD,
    )
    template = measure_artifact(
        args.output,
        template_texts,
        template_labels,
        ROUTER_CONFIDENCE_THRESHOLD,
    )
    update_meta(
        args.output,
        {
            "eval_top1": round(natural["top1"], 4),
            "eval_macro_f1": round(natural["macro_f1"], 4),
            "eval_correct": int(natural["correct"]),
            "eval_ci": round(natural["ci"], 4),
            "eval_coverage": round(natural["coverage"], 4),
            "eval_selective_accuracy": round(
                natural["selective"],
                4,
            ),
            "eval_ece": round(natural["ece"], 4),
            "eval_brier": round(natural["brier"], 4),
            "template_top1": round(template["top1"], 4),
            "template_macro_f1": round(template["macro_f1"], 4),
            "template_correct": int(template["correct"]),
            "template_coverage": round(template["coverage"], 4),
            "template_selective_accuracy": round(
                template["selective"],
                4,
            ),
        },
    )
    print(
        f"natural: top-1 {natural['top1']:.3f}, "
        f"macro-F1 {natural['macro_f1']:.3f}, "
        f"покрытие {natural['coverage']:.3f}, "
        f"точность {natural['selective']:.3f}"
    )
    print(
        f"template: top-1 {template['top1']:.3f}, "
        f"macro-F1 {template['macro_f1']:.3f}, "
        f"покрытие {template['coverage']:.3f}, "
        f"точность {template['selective']:.3f}"
    )

    size = args.output.stat().st_size / 1e6
    print(f"Веса: {args.output} ({size:.2f} МБ)")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Обучает роутер и сохраняет веса."""

    args = parse_args(argv)

    return finish_training(args, prepare_training(args))

if __name__ == "__main__":
    raise SystemExit(main())
