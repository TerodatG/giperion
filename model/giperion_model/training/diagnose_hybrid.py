# GiperionModel/giperion_model/training/diagnose_hybrid.py            v001
# Диагностика гибридной модели: знакомые и новые слова отдельно.

import json

import torch

from giperion_model.config import MODELS_DIR
from giperion_model.training.build_dataset import CLASSIFICATION_FILE
from giperion_model.training.char_tokenizer import CharTokenizer
from giperion_model.training.model_charcnn import HybridTextClassifier
from giperion_model.training.tokenizer import (
    TOKENIZER_FILE,
    WordTokenizer,
    tokenize_text,
)
from giperion_model.training.train_classifier import (
    DEVICE,
    MAX_LEN,
    split_examples,
)

CHECKPOINT_FILE = MODELS_DIR / "hybrid.pt"


def load_model() -> tuple[HybridTextClassifier, list[str]]:
    """Загружает лучшую гибридную модель."""

    checkpoint = torch.load(
        CHECKPOINT_FILE,
        map_location=DEVICE,
        weights_only=True,
    )

    word_tokenizer = WordTokenizer.load(TOKENIZER_FILE)
    char_tokenizer = CharTokenizer.load()

    model = HybridTextClassifier(
        vocab_size=word_tokenizer.vocab_size,
        char_vocab_size=char_tokenizer.vocab_size,
        num_classes=len(checkpoint["labels"]),
        pad_id=word_tokenizer.pad_id,
    ).to(DEVICE)

    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    return model, checkpoint["labels"]


def main() -> None:
    """Считает точность на знакомых и новых словах."""

    model, labels = load_model()

    word_tokenizer = WordTokenizer.load(TOKENIZER_FILE)
    char_tokenizer = CharTokenizer.load()

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

    stats = {
        "familiar": [0, 0],
        "novel": [0, 0],
    }

    for example in val_examples:
        ids = word_tokenizer.encode(
            example["text"],
        )[:MAX_LEN]

        ids = ids + [word_tokenizer.pad_id] * (
            MAX_LEN - len(ids)
        )

        chars = char_tokenizer.encode(example["text"])

        tokens = torch.tensor(
            [ids],
            dtype=torch.long,
        ).to(DEVICE)

        char_tensor = torch.tensor(
            [chars],
            dtype=torch.long,
        ).to(DEVICE)

        with torch.no_grad():
            prediction = int(
                model(tokens, char_tensor)
                .argmax(dim=1)
                .item()
            )

        is_correct = (
            labels[prediction] == example["label"]
        )

        text_tokens = tokenize_text(example["text"])

        is_familiar = all(
            token in train_tokens
            for token in text_tokens
        )

        group = "familiar" if is_familiar else "novel"
        stats[group][0] += int(is_correct)
        stats[group][1] += 1

    total = stats["familiar"][1] + stats["novel"][1]
    correct = stats["familiar"][0] + stats["novel"][0]

    print("=== Диагностика гибридной модели ===")

    if not total:
        print("Нет проверочных примеров — диагностика невозможна.")
        return

    print(f"Всего: {total}, точность: {correct / total:.3f}")
    print()

    for group, title in (
        ("familiar", "Все слова знакомы"),
        ("novel", "Есть новые слова"),
    ):
        hit, count = stats[group]

        if count:
            rate = hit / count
            print(f"{title}: {count} ({rate:.3f})")


if __name__ == "__main__":
    main()
