# Giperion/tools/eval_intent_model.py                               v002
# Оценка классификатора намерений на отложенном наборе фраз.
# Последнее изменение: macro-F1, покрытие и порог для CI.

import argparse
import json
from collections import Counter

import torch

from config import DATA_DIR, LOGS_DIR, MODELS_DIR
from giperion_model.language.intent_handler import load_intents
from giperion_model.neural_engine import CONFIDENCE_THRESHOLD
from giperion_model.training.char_tokenizer import (
    CHAR_TOKENIZER_FILE,
    CharTokenizer,
)
from giperion_model.training.model_charcnn import HybridTextClassifier
from giperion_model.training.tokenizer import TOKENIZER_FILE, WordTokenizer
from shared.text_tools import normalize_message

EVAL_FILE = DATA_DIR / "eval_set.json"
CLASSIFIER_FILE = MODELS_DIR / "hybrid.pt"
REPORT_FILE = LOGS_DIR / "eval_report.txt"

DEFAULT_MIN_TOP1 = 0.60
DEFAULT_MIN_MACRO_F1 = 0.55

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


def intent_patterns() -> set[str]:
    """Собирает нормализованные фразы, которые уже есть в обучении."""

    patterns = set()

    for intent in load_intents():
        for pattern in intent.get("patterns", []):
            if isinstance(pattern, str):
                patterns.add(normalize_message(pattern))

    return patterns


def load_examples(
    labels: set[str],
) -> tuple[list[dict], list[str]]:
    """Читает отложенный набор и отбрасывает пересечения с обучением.

    Возвращает примеры для проверки и список замечаний.
    """

    with EVAL_FILE.open("r", encoding="utf-8") as file:
        document = json.load(file)

    known_patterns = intent_patterns()

    examples = []
    notes = []

    for item in document.get("phrases", []):
        text = str(item.get("text", "")).strip()
        label = item.get("label")

        if not text or not isinstance(label, str):
            notes.append(f"пропущена кривая запись: {item}")

            continue

        if label not in labels:
            notes.append(f"неизвестный тег {label}: «{text}»")

            continue

        if normalize_message(text) in known_patterns:
            notes.append(f"уже есть в обучении: «{text}»")

            continue

        examples.append({"text": text, "label": label})

    return examples, notes


def build_model() -> tuple[HybridTextClassifier, list[str], int]:
    """Загружает гибридный классификатор из чекпоинта."""

    checkpoint = torch.load(
        CLASSIFIER_FILE,
        map_location=DEVICE,
        weights_only=True,
    )

    word_tokenizer = WordTokenizer.load(TOKENIZER_FILE)
    char_tokenizer = CharTokenizer.load(CHAR_TOKENIZER_FILE)

    model = HybridTextClassifier(
        vocab_size=word_tokenizer.vocab_size,
        char_vocab_size=char_tokenizer.vocab_size,
        num_classes=len(checkpoint["labels"]),
        pad_id=word_tokenizer.pad_id,
    ).to(DEVICE)

    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    return model, checkpoint["labels"], checkpoint["max_len"]


def classify(
    model: HybridTextClassifier,
    labels: list[str],
    max_len: int,
    text: str,
    word_tokenizer: WordTokenizer,
    char_tokenizer: CharTokenizer,
) -> tuple[str, float]:
    """Возвращает предсказанный тег и уверенность модели."""

    ids = word_tokenizer.encode(text)[:max_len]
    ids = ids + [word_tokenizer.pad_id] * (max_len - len(ids))

    chars = char_tokenizer.encode(text)

    tokens = torch.tensor([ids], dtype=torch.long, device=DEVICE)
    char_tensor = torch.tensor(
        [chars],
        dtype=torch.long,
        device=DEVICE,
    )

    with torch.no_grad():
        logits = model(tokens, char_tensor)
        probabilities = torch.softmax(logits, dim=1)

    index = int(probabilities.argmax(dim=1).item())

    return labels[index], float(probabilities[0, index].item())


def predict_all(
    model: HybridTextClassifier,
    labels: list[str],
    max_len: int,
    examples: list[dict],
    word_tokenizer: WordTokenizer,
    char_tokenizer: CharTokenizer,
) -> list[dict]:
    """Классифицирует весь набор и сохраняет уверенность."""

    rows = []

    for example in examples:
        predicted, confidence = classify(
            model,
            labels,
            max_len,
            example["text"],
            word_tokenizer,
            char_tokenizer,
        )

        rows.append(
            {
                "text": example["text"],
                "label": example["label"],
                "predicted": predicted,
                "confidence": confidence,
            }
        )

    return rows


def class_metrics(
    truths: list[str],
    predictions: list[str],
) -> dict[str, dict[str, float]]:
    """Считает precision, recall и F1 для каждого класса."""

    pairs = list(zip(truths, predictions, strict=False))
    result: dict[str, dict[str, float]] = {}

    for label in sorted(set(truths)):
        true_positive = sum(
            1
            for truth, predicted in pairs
            if truth == label and predicted == label
        )
        predicted_positive = sum(
            1 for _truth, predicted in pairs if predicted == label
        )
        actual_positive = sum(
            1 for truth, _predicted in pairs if truth == label
        )

        precision = (
            true_positive / predicted_positive
            if predicted_positive
            else 0.0
        )
        recall = (
            true_positive / actual_positive
            if actual_positive
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        result[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": float(actual_positive),
        }

    return result


def macro_f1(per_class: dict[str, dict[str, float]]) -> float:
    """Средний F1 по классам: редкие классы весят как частые."""

    if not per_class:
        return 0.0

    return sum(item["f1"] for item in per_class.values()) / len(
        per_class
    )


def selective_metrics(
    truths: list[str],
    predictions: list[str],
    confidences: list[float],
    threshold: float,
) -> tuple[float, float]:
    """Покрытие и точность на ответах не ниже порога."""

    covered = [
        (truth, predicted)
        for truth, predicted, confidence in zip(
            truths,
            predictions,
            confidences,
            strict=False,
        )
        if confidence >= threshold
    ]

    if not covered:
        return 0.0, 0.0

    correct = sum(
        1 for truth, predicted in covered if truth == predicted
    )

    return len(covered) / len(truths), correct / len(covered)


def build_report(
    rows: list[dict],
    notes: list[str],
) -> tuple[str, dict[str, float]]:
    """Собирает текст отчёта и сводные метрики."""

    truths = [row["label"] for row in rows]
    predictions = [row["predicted"] for row in rows]
    confidences = [row["confidence"] for row in rows]

    correct = sum(
        1 for truth, predicted in zip(
            truths, predictions, strict=False
        )
        if truth == predicted
    )
    accuracy = correct / len(rows)

    per_class = class_metrics(truths, predictions)
    average_f1 = macro_f1(per_class)
    coverage, selective = selective_metrics(
        truths,
        predictions,
        confidences,
        CONFIDENCE_THRESHOLD,
    )

    confusions = Counter(
        (row["label"], row["predicted"])
        for row in rows
        if row["label"] != row["predicted"]
    )
    errors = [
        row for row in rows if row["label"] != row["predicted"]
    ]
    weak_classes = sorted(
        (
            (item["f1"], label, item)
            for label, item in per_class.items()
        )
    )

    lines = [
        "=== Оценка классификатора Giperion ===",
        f"Модель: {CLASSIFIER_FILE.name}",
        f"Устройство: {DEVICE}",
        f"Фраз в проверке: {len(rows)}",
        f"Классов: {len(per_class)}",
        f"Верных ответов: {correct}",
        f"Точность (top-1): {accuracy:.3f}",
        f"Macro-F1: {average_f1:.3f}",
        f"Покрытие (уверенность ≥ {CONFIDENCE_THRESHOLD:.2f}): "
        f"{coverage:.3f}",
        f"Точность на покрытых: {selective:.3f}",
        "",
        "--- Слабые классы (F1 < 1.0) ---",
    ]

    for class_f1, label, item in weak_classes:
        if class_f1 >= 1.0:
            continue

        lines.append(
            f"{label}: F1 {class_f1:.2f}, "
            f"P {item['precision']:.2f}, "
            f"R {item['recall']:.2f} "
            f"({int(item['support'])} примеров)"
        )

    lines.extend(["", "--- Частые путаницы ---"])

    for (true_label, predicted), count in confusions.most_common(15):
        lines.append(f"{true_label} → {predicted}: {count}")

    lines.extend(["", "--- Ошибки ---"])

    for row in errors:
        lines.append(
            f"«{row['text']}»: верно {row['label']}, "
            f"модель {row['predicted']} "
            f"({row['confidence']:.2f})"
        )

    if notes:
        lines.extend(["", "--- Замечания по набору ---"])
        lines.extend(notes)

    metrics = {
        "accuracy": accuracy,
        "macro_f1": average_f1,
        "coverage": coverage,
        "selective_accuracy": selective,
        "correct": float(correct),
        "errors": float(len(errors)),
    }

    return "\n".join(lines), metrics


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Разбирает ключи запуска."""

    parser = argparse.ArgumentParser(
        description=(
            "Оценка классификатора намерений на отложенном наборе."
        )
    )
    parser.add_argument(
        "--fail",
        action="store_true",
        help="вернуть код 1, если метрики ниже порогов",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="считать замечания к набору ошибкой",
    )
    parser.add_argument(
        "--min-top1",
        type=float,
        default=DEFAULT_MIN_TOP1,
        help="минимальная точность top-1",
    )
    parser.add_argument(
        "--min-macro-f1",
        type=float,
        default=DEFAULT_MIN_MACRO_F1,
        help="минимальный macro-F1",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Проверяет модель, пишет отчёт и применяет пороги."""

    args = parse_args(argv)

    model, labels, max_len = build_model()

    word_tokenizer = WordTokenizer.load(TOKENIZER_FILE)
    char_tokenizer = CharTokenizer.load(CHAR_TOKENIZER_FILE)

    examples, notes = load_examples(set(labels))

    if not examples:
        print("Отложенный набор пуст — нечего проверять.")

        return 1 if args.fail else 0

    rows = predict_all(
        model,
        labels,
        max_len,
        examples,
        word_tokenizer,
        char_tokenizer,
    )
    report, metrics = build_report(rows, notes)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")

    print(
        f"Точность: {metrics['accuracy']:.3f} "
        f"({int(metrics['correct'])} из {len(rows)}), "
        f"macro-F1: {metrics['macro_f1']:.3f}, "
        f"ошибок: {int(metrics['errors'])}"
    )
    print(f"Отчёт: {REPORT_FILE}")

    failures = []

    if metrics["accuracy"] < args.min_top1:
        failures.append(
            f"top-1 {metrics['accuracy']:.3f} < "
            f"{args.min_top1:.3f}"
        )

    if metrics["macro_f1"] < args.min_macro_f1:
        failures.append(
            f"macro-F1 {metrics['macro_f1']:.3f} < "
            f"{args.min_macro_f1:.3f}"
        )

    if args.strict and notes:
        failures.append(
            f"замечаний к набору: {len(notes)}"
        )

    if failures and args.fail:
        print("Порог не пройден:")

        for failure in failures:
            print(f"- {failure}")

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
