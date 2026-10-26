# Giperion/training/train_classifier.py                              v002
# Обучение классификатора намерений на GPU.
# Последнее изменение: разделение по классам, аугментация, регуляризация.

import json
import random

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from giperion_model.config import MODELS_DIR
from giperion_model.training.build_dataset import CLASSIFICATION_FILE
from giperion_model.training.model_classifier import (
    TextClassifier,
    parameter_count,
)
from giperion_model.training.tokenizer import TOKENIZER_FILE, WordTokenizer

CHECKPOINT_FILE = MODELS_DIR / "classifier.pt"
LABELS_FILE = MODELS_DIR / "classifier_labels.json"

BATCH_SIZE = 64
EPOCHS = 30
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
LABEL_SMOOTHING = 0.1
AUGMENT_COPIES = 2
MAX_LEN = 32
TRAIN_SHARE = 0.9
SEED = 42

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


class IntentDataset(Dataset):
    """Примеры «текст → метка», превращённые в тензоры."""

    def __init__(
        self,
        examples: list[dict],
        label_to_id: dict[str, int],
        tokenizer: WordTokenizer,
        max_len: int = MAX_LEN,
    ) -> None:
        self.examples = examples
        self.label_to_id = label_to_id
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self) -> int:
        """Число примеров."""

        return len(self.examples)

    def __getitem__(
        self,
        index: int,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Возвращает последовательность id и метку."""

        example = self.examples[index]

        ids = self.tokenizer.encode(example["text"])
        ids = ids[: self.max_len]

        # Дополняем короткую фразу до фиксированной длины.
        padding = [self.tokenizer.pad_id] * (
            self.max_len - len(ids)
        )
        ids = ids + padding

        label = self.label_to_id[example["label"]]

        return (
            torch.tensor(ids, dtype=torch.long),
            torch.tensor(label, dtype=torch.long),
        )


def split_examples(
    examples: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Делит по классам: каждый класс есть в обеих выборках."""

    by_label: dict[str, list[dict]] = {}

    for example in examples:
        by_label.setdefault(
            example["label"],
            [],
        ).append(example)

    rng = random.Random(SEED)
    train_examples = []
    val_examples = []

    for label in sorted(by_label):
        group = list(by_label[label])
        rng.shuffle(group)

        holdout = max(
            1,
            int(round(len(group) * (1 - TRAIN_SHARE))),
        )

        val_examples.extend(group[:holdout])
        train_examples.extend(group[holdout:])

    rng.shuffle(train_examples)
    rng.shuffle(val_examples)

    return train_examples, val_examples


def augment_text(
    text: str,
    rng: random.Random,
) -> str | None:
    """Лёгкий шум: перестановка или удаление слова."""

    words = text.split()

    if len(words) < 2:
        return None

    if rng.random() < 0.5:
        first = rng.randrange(len(words))
        second = rng.randrange(len(words))

        words[first], words[second] = (
            words[second],
            words[first],
        )
    else:
        del words[rng.randrange(len(words))]

    return " ".join(words)


def augment_examples(
    examples: list[dict],
) -> list[dict]:
    """Добавляет шумовые варианты каждой фразы.

    Работает только после разделения, чтобы проверочная
    выборка осталась чистой.
    """

    rng = random.Random(SEED)
    augmented = list(examples)

    for example in examples:
        for _ in range(AUGMENT_COPIES):
            variant = augment_text(
                example["text"],
                rng,
            )

            if variant:
                augmented.append(
                    {
                        "text": variant,
                        "label": example["label"],
                    }
                )

    return augmented


def evaluate(
    model: nn.Module,
    loader: DataLoader,
) -> float:
    """Считает долю верных ответов модели без обучения."""

    model.eval()
    correct = 0
    total = 0

    with torch.no_grad():
        for tokens, targets in loader:
            tokens = tokens.to(DEVICE)
            targets = targets.to(DEVICE)

            logits = model(tokens)
            predictions = logits.argmax(dim=1)

            correct += (
                predictions == targets
            ).sum().item()
            total += targets.size(0)

    return correct / max(total, 1)


def save_checkpoint(
    model: nn.Module,
    labels: list[str],
) -> None:
    """Сохраняет веса модели и список классов."""

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "model_state": model.state_dict(),
            "labels": labels,
            "max_len": MAX_LEN,
            "vocab_size": model.embedding.num_embeddings,
        },
        CHECKPOINT_FILE,
    )

    with LABELS_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(labels, file, ensure_ascii=False, indent=2)


def train() -> None:
    """Обучает классификатор и печатает статистику по эпохам."""

    torch.manual_seed(SEED)

    with CLASSIFICATION_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        examples = json.load(file)

    labels = sorted(
        {example["label"] for example in examples}
    )
    label_to_id = {
        label: index
        for index, label in enumerate(labels)
    }

    tokenizer = WordTokenizer.load(TOKENIZER_FILE)

    train_examples, val_examples = split_examples(
        examples
    )

    train_examples = augment_examples(train_examples)

    train_loader = DataLoader(
        IntentDataset(
            train_examples,
            label_to_id,
            tokenizer,
        ),
        batch_size=BATCH_SIZE,
        shuffle=True,
        pin_memory=True,
    )

    val_loader = DataLoader(
        IntentDataset(
            val_examples,
            label_to_id,
            tokenizer,
        ),
        batch_size=BATCH_SIZE,
        pin_memory=True,
    )

    model = TextClassifier(
        vocab_size=tokenizer.vocab_size,
        num_classes=len(labels),
    ).to(DEVICE)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    criterion = nn.CrossEntropyLoss(
        label_smoothing=LABEL_SMOOTHING,
    )

    print("=== Обучение классификатора Giperion ===")
    print(f"Устройство: {DEVICE}")
    if DEVICE.type == "cuda":
        print(f"Видеокарта: {torch.cuda.get_device_name(0)}")
    print(f"Классов: {len(labels)}")
    print(
        f"Обучающих: {len(train_examples)}, "
        f"проверочных: {len(val_examples)}"
    )
    print(f"Параметров модели: {parameter_count(model)}")
    print()

    best_val_accuracy = 0.0

    for epoch in range(1, EPOCHS + 1):
        model.train()
        epoch_loss = 0.0
        seen = 0

        for tokens, targets in train_loader:
            tokens = tokens.to(DEVICE)
            targets = targets.to(DEVICE)

            optimizer.zero_grad()

            logits = model(tokens)
            loss = criterion(logits, targets)

            loss.backward()
            optimizer.step()

            epoch_loss += loss.item() * targets.size(0)
            seen += targets.size(0)

        train_accuracy = evaluate(model, train_loader)
        val_accuracy = evaluate(model, val_loader)

        if val_accuracy >= best_val_accuracy:
            best_val_accuracy = val_accuracy
            save_checkpoint(model, labels)

        print(
            f"Эпоха {epoch:02d}/{EPOCHS}: "
            f"loss={epoch_loss / max(seen, 1):.4f} "
            f"train={train_accuracy:.3f} "
            f"val={val_accuracy:.3f}"
        )

    print()
    print(f"Лучшая точность: {best_val_accuracy:.3f}")
    print(f"Модель сохранена: {CHECKPOINT_FILE}")


if __name__ == "__main__":
    train()
