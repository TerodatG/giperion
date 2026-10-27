# GiperionModel/giperion_model/training/diagnose_classifier.py        v001
# Диагностика классификатора: где и почему он ошибается на проверке.

import json

import torch

from giperion_model.training.build_dataset import CLASSIFICATION_FILE
from giperion_model.training.model_classifier import TextClassifier
from giperion_model.training.tokenizer import (
    TOKENIZER_FILE,
    WordTokenizer,
    tokenize_text,
)
from giperion_model.training.train_classifier import (
    CHECKPOINT_FILE,
    DEVICE,
    MAX_LEN,
    split_examples,
)

EXAMPLES_TO_SHOW = 12


def load_model() -> tuple[TextClassifier, list[str]]:
    """Загружает лучшую сохранённую модель."""

    checkpoint = torch.load(
        CHECKPOINT_FILE,
        map_location=DEVICE,
        weights_only=True,
    )

    tokenizer = WordTokenizer.load(TOKENIZER_FILE)

    model = TextClassifier(
        vocab_size=tokenizer.vocab_size,
        num_classes=len(checkpoint["labels"]),
    ).to(DEVICE)

    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    return model, checkpoint["labels"]


def predict(
    model: TextClassifier,
    tokenizer: WordTokenizer,
    text: str,
) -> tuple[int, float]:
    """Возвращает индекс класса и уверенность модели."""

    ids = tokenizer.encode(text)[:MAX_LEN]
    ids = ids + [tokenizer.pad_id] * (MAX_LEN - len(ids))

    tokens = torch.tensor(
        ids,
        dtype=torch.long,
    ).unsqueeze(0).to(DEVICE)

    with torch.no_grad():
        logits = model(tokens)
        probabilities = torch.softmax(logits, dim=1)

    index = int(probabilities.argmax(dim=1).item())
    confidence = float(probabilities[0, index].item())

    return index, confidence


def main() -> None:
    """Печатает точность, новизну слов и примеры ошибок."""

    model, labels = load_model()
    tokenizer = WordTokenizer.load(TOKENIZER_FILE)

    with CLASSIFICATION_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        examples = json.load(file)

    train_examples, val_examples = split_examples(
        examples
    )

    train_tokens = set()

    for example in train_examples:
        train_tokens.update(
            tokenize_text(example["text"])
        )

    correct = 0
    familiar_correct = 0
    familiar_total = 0
    novel_correct = 0
    novel_total = 0
    errors = []

    for example in val_examples:
        index, confidence = predict(
            model,
            tokenizer,
            example["text"],
        )

        predicted_label = labels[index]
        is_correct = predicted_label == example["label"]

        correct += int(is_correct)

        tokens = tokenize_text(example["text"])
        is_familiar = all(
            token in train_tokens
            for token in tokens
        )

        if is_familiar:
            familiar_total += 1
            familiar_correct += int(is_correct)
        else:
            novel_total += 1
            novel_correct += int(is_correct)

        if not is_correct:
            errors.append(
                (
                    example["text"],
                    example["label"],
                    predicted_label,
                    confidence,
                )
            )

    total = len(val_examples)

    print("=== Диагностика классификатора ===")
    print(f"Проверочных примеров: {total}")

    if not total:
        print("Точность: нет данных.")
        return

    print(f"Точность: {correct / total:.3f}")
    print()

    if familiar_total:
        print(
            f"Все слова знакомы: {familiar_total} "
            f"({familiar_correct / familiar_total:.3f})"
        )

    if novel_total:
        print(
            f"Есть новые слова: {novel_total} "
            f"({novel_correct / novel_total:.3f})"
        )

    print()
    print(f"--- Ошибки (показано {min(len(errors), EXAMPLES_TO_SHOW)} из {len(errors)}) ---")

    for text, true_label, predicted, confidence in errors[
        :EXAMPLES_TO_SHOW
    ]:
        print(f"Текст:    {text}")
        print(f"Верно:    {true_label}")
        print(f"Модель:   {predicted} ({confidence:.2f})")
        print()


if __name__ == "__main__":
    main()
