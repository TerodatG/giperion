# Giperion/tools/eval_intent_model.py                               v001
# Оценка классификатора намерений на отложенном наборе фраз.
# Последнее изменение: первый вариант — точность, путаница классов, отчёт в logs/.

import json
from collections import Counter

import torch
from giperion_model.language.intent_handler import load_intents
from giperion_model.training.char_tokenizer import (
    CHAR_TOKENIZER_FILE,
    CharTokenizer,
)
from giperion_model.training.model_charcnn import HybridTextClassifier
from giperion_model.training.tokenizer import TOKENIZER_FILE, WordTokenizer

from config import DATA_DIR, LOGS_DIR, MODELS_DIR
from shared.text_tools import normalize_message

EVAL_FILE = DATA_DIR / "eval_set.json"
CLASSIFIER_FILE = MODELS_DIR / "hybrid.pt"
REPORT_FILE = LOGS_DIR / "eval_report.txt"

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
        weights_only=False,
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


def main() -> None:
    """Проверяет модель и пишет отчёт в logs/eval_report.txt."""

    model, labels, max_len = build_model()

    word_tokenizer = WordTokenizer.load(TOKENIZER_FILE)
    char_tokenizer = CharTokenizer.load(CHAR_TOKENIZER_FILE)

    examples, notes = load_examples(set(labels))

    if not examples:
        print("Отложенный набор пуст — нечего проверять.")

        return

    per_class_total = Counter()
    per_class_correct = Counter()
    confusions = Counter()
    errors = []

    for example in examples:
        predicted, confidence = classify(
            model,
            labels,
            max_len,
            example["text"],
            word_tokenizer,
            char_tokenizer,
        )

        per_class_total[example["label"]] += 1

        if predicted == example["label"]:
            per_class_correct[example["label"]] += 1
        else:
            confusions[(example["label"], predicted)] += 1
            errors.append(
                (
                    example["text"],
                    example["label"],
                    predicted,
                    confidence,
                )
            )

    correct = sum(per_class_correct.values())
    accuracy = correct / len(examples)

    weak_classes = sorted(
        (
            (per_class_correct[label] / per_class_total[label], label)
            for label in per_class_total
        )
    )

    lines = [
        "=== Оценка классификатора Giperion ===",
        f"Модель: {CLASSIFIER_FILE.name}",
        f"Устройство: {DEVICE}",
        f"Фраз в проверке: {len(examples)}",
        f"Верных ответов: {correct}",
        f"Точность (top-1): {accuracy:.3f}",
        "",
        "--- Слабые классы (точность по классу) ---",
    ]

    for class_accuracy, label in weak_classes:
        if class_accuracy < 1.0:
            lines.append(
                f"{label}: {class_accuracy:.2f} "
                f"({per_class_correct[label]}/{per_class_total[label]})"
            )

    lines.extend(["", "--- Частые путаницы ---"])

    for (true_label, predicted), count in confusions.most_common(15):
        lines.append(f"{true_label} → {predicted}: {count}")

    lines.extend(["", "--- Ошибки ---"])

    for text, true_label, predicted, confidence in errors:
        lines.append(
            f"«{text}»: верно {true_label}, "
            f"модель {predicted} ({confidence:.2f})"
        )

    if notes:
        lines.extend(["", "--- Замечания по набору ---"])
        lines.extend(notes)

    report = "\n".join(lines)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")

    print(
        f"Точность: {accuracy:.3f} "
        f"({correct} из {len(examples)}), "
        f"ошибок: {len(errors)}"
    )
    print(f"Отчёт: {REPORT_FILE}")


if __name__ == "__main__":
    main()
