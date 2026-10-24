# Giperion/training/train_charcnn.py                               v003
# Обучение гибридного классификатора: слова + символы.
# Последнее изменение: эксперимент с проверочной выборкой пишется в hybrid_val.pt.

import json
import sys

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from config import MODELS_DIR
from giperion.training.build_dataset import CLASSIFICATION_FILE
from giperion.training.char_tokenizer import (
    CHAR_TOKENIZER_FILE,
    CharTokenizer,
)
from giperion.training.model_charcnn import HybridTextClassifier
from giperion.training.model_classifier import parameter_count
from giperion.training.tokenizer import WordTokenizer, TOKENIZER_FILE
from giperion.training.train_classifier import (
    BATCH_SIZE,
    DEVICE,
    EPOCHS,
    LABEL_SMOOTHING,
    LEARNING_RATE,
    MAX_LEN,
    SEED,
    WEIGHT_DECAY,
    augment_examples,
    split_examples,
)

CHECKPOINT_FILE = MODELS_DIR / "hybrid.pt"

# Экспериментальная модель (обучение с проверочной выборкой) пишется отдельно,
# чтобы случайный запуск не подменил рабочую модель бота.
EXPERIMENT_FILE = MODELS_DIR / "hybrid_val.pt"


def checkpoint_file(full: bool):
    """Путь чекпоинта: рабочая модель или экспериментальная."""

    return CHECKPOINT_FILE if full else EXPERIMENT_FILE


class HybridDataset(Dataset):
    """Примеры сразу в двух формах: токенами и символами."""

    def __init__(
        self,
        examples: list[dict],
        word_tokenizer: WordTokenizer,
        char_tokenizer: CharTokenizer,
    ) -> None:
        self.samples = []

        for example in examples:
            ids = word_tokenizer.encode(
                example["text"],
            )[:MAX_LEN]

            ids = ids + [word_tokenizer.pad_id] * (
                MAX_LEN - len(ids)
            )

            chars = char_tokenizer.encode(
                example["text"],
            )

            self.samples.append(
                {
                    "tokens": torch.tensor(
                        ids,
                        dtype=torch.long,
                    ),
                    "chars": torch.tensor(
                        chars,
                        dtype=torch.long,
                    ),
                    "label": example["label"],
                }
            )

    def __len__(self) -> int:
        """Число примеров."""

        return len(self.samples)

    def __getitem__(self, index: int) -> dict:
        """Возвращает один пример."""

        return self.samples[index]


def save_checkpoint(
    model: HybridTextClassifier,
    labels: list[str],
    path,
) -> None:
    """Сохраняет веса модели и её словарь классов."""

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "model_state": model.state_dict(),
            "labels": labels,
            "max_len": MAX_LEN,
        },
        path,
    )


def batch_targets(
    batch_labels: list[str],
    labels: list[str],
) -> torch.Tensor:
    """Переводит строковые метки батча в id классов."""

    return torch.tensor(
        [labels.index(label) for label in batch_labels],
        dtype=torch.long,
        device=DEVICE,
    )


def print_errors(
    model: HybridTextClassifier,
    dataset: HybridDataset,
    labels: list[str],
    examples: list[dict],
    limit: int = 10,
) -> None:
    """Показывает, где лучшая модель ошиблась на проверке."""

    model.eval()

    predictions = []
    confidences = []

    for sample in dataset:
        tokens = sample["tokens"].unsqueeze(0).to(DEVICE)
        chars = sample["chars"].unsqueeze(0).to(DEVICE)

        with torch.no_grad():
            logits = model(tokens, chars)
            probabilities = torch.softmax(logits, dim=1)

        index = int(probabilities.argmax(dim=1).item())
        confidence = float(probabilities[0, index].item())

        predictions.append(index)
        confidences.append(confidence)

    errors = []

    for position, example in enumerate(examples):
        predicted = labels[predictions[position]]

        if predicted != example["label"]:
            errors.append(
                (
                    example["text"],
                    example["label"],
                    predicted,
                    confidences[position],
                )
            )

    print(f"--- Ошибок: {len(errors)} из {len(examples)} ---")

    for text, true_label, predicted, confidence in errors[:limit]:
        print(f"Текст:    {text}")
        print(f"Верно:    {true_label}")
        print(f"Модель:   {predicted} ({confidence:.2f})")
        print()


def evaluate(
    model: HybridTextClassifier,
    val_loader: DataLoader,
    labels: list[str],
) -> float:
    """Точность модели на проверочной выборке."""

    model.eval()
    correct = 0

    with torch.no_grad():
        for batch in val_loader:
            tokens = batch["tokens"].to(DEVICE)
            chars = batch["chars"].to(DEVICE)

            targets = batch_targets(
                batch["label"],
                labels,
            )

            logits = model(tokens, chars)

            correct += int(
                (logits.argmax(dim=1) == targets)
                .sum()
                .item()
            )

    return correct / len(val_loader.dataset)


def train(full: bool = False) -> None:
    """Обучает гибридную модель и показывает её ошибки.

    full=True — финальное обучение на всём датасете
    без проверочной выборки (для работы бота).
    """

    torch.manual_seed(SEED)

    checkpoint = checkpoint_file(full)

    with CLASSIFICATION_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        examples = json.load(file)

    word_tokenizer = WordTokenizer.load(TOKENIZER_FILE)
    char_tokenizer = CharTokenizer.load(CHAR_TOKENIZER_FILE)

    if full:
        train_examples = augment_examples(examples)
        val_examples = []
    else:
        train_examples, val_examples = split_examples(
            examples
        )

        train_examples = augment_examples(train_examples)

    labels = sorted({item["label"] for item in examples})

    train_dataset = HybridDataset(
        train_examples,
        word_tokenizer,
        char_tokenizer,
    )

    val_dataset = HybridDataset(
        val_examples,
        word_tokenizer,
        char_tokenizer,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        pin_memory=True,
    )

    val_loader = (
        None
        if not val_examples
        else DataLoader(
            val_dataset,
            batch_size=BATCH_SIZE,
            pin_memory=True,
        )
    )

    model = HybridTextClassifier(
        vocab_size=word_tokenizer.vocab_size,
        char_vocab_size=char_tokenizer.vocab_size,
        num_classes=len(labels),
        pad_id=word_tokenizer.pad_id,
    ).to(DEVICE)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
    )

    criterion = nn.CrossEntropyLoss(
        label_smoothing=LABEL_SMOOTHING,
    )

    mode_title = (
        "финальное на всём датасете"
        if full
        else "с проверочной выборкой"
    )

    print(f"=== Гибридный классификатор Giperion ({mode_title}) ===")
    print(f"Устройство: {DEVICE}")
    print(f"Классов: {len(labels)}")
    print(f"Обучающих: {len(train_dataset)}")

    if val_loader:
        print(f"Проверочных: {len(val_dataset)}")

    print(f"Параметров модели: {parameter_count(model)}")
    print()

    best_accuracy = -1.0

    for epoch in range(1, EPOCHS + 1):
        model.train()
        epoch_loss = 0.0
        seen = 0
        correct = 0

        for batch in train_loader:
            tokens = batch["tokens"].to(DEVICE)
            chars = batch["chars"].to(DEVICE)

            targets = batch_targets(
                batch["label"],
                labels,
            )

            optimizer.zero_grad()

            logits = model(tokens, chars)
            loss = criterion(logits, targets)

            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0,
            )

            optimizer.step()

            epoch_loss += loss.item() * targets.size(0)
            seen += targets.size(0)

            correct += int(
                (logits.argmax(dim=1) == targets)
                .sum()
                .item()
            )

        train_accuracy = correct / max(seen, 1)

        if val_loader is None:
            # Нет проверки — сохраняем после каждой эпохи,
            # в файле остаётся последняя версия.
            save_checkpoint(model, labels, checkpoint)
            val_accuracy = 0.0
        else:
            val_accuracy = evaluate(
                model,
                val_loader,
                labels,
            )

            if val_accuracy > best_accuracy:
                best_accuracy = val_accuracy
                save_checkpoint(model, labels, checkpoint)

        report = (
            f"Эпоха {epoch:02d}/{EPOCHS}: "
            f"loss={epoch_loss / max(seen, 1):.4f} "
            f"train={train_accuracy:.3f}"
        )

        if val_loader:
            report += f" val={val_accuracy:.3f}"

        print(report)

    print()

    if best_accuracy >= 0:
        print(f"Лучшая точность: {best_accuracy:.3f}")
    else:
        print("Проверочная выборка не использовалась.")

    print(f"Модель сохранена: {checkpoint}")
    print()

    if not val_examples:
        return

    # Перезагружаем лучшие веса для честного показа ошибок.
    best_checkpoint = torch.load(
        checkpoint,
        map_location=DEVICE,
        weights_only=False,
    )

    model.load_state_dict(best_checkpoint["model_state"])

    print_errors(
        model,
        val_dataset,
        labels,
        val_examples,
    )


if __name__ == "__main__":
    train(full="--full" in sys.argv)
