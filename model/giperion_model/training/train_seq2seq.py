# GiperionModel/giperion_model/training/train_seq2seq.py              v002
# Обучение генеративной модели ответов Giperion.
# Последнее изменение: примеры печатаются с лучшими сохранёнными весами.

import json
import os
import random
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from giperion_model.config import MODELS_DIR, resolve_device
from giperion_model.storage import save_torch
from giperion_model.training.build_dataset import PAIRS_FILE
from giperion_model.training.model_seq2seq import Seq2Seq
from giperion_model.training.tokenizer import TOKENIZER_FILE, WordTokenizer

CHECKPOINT_FILE = MODELS_DIR / "seq2seq.pt"
OUTPUT_FILE = Path(
    os.environ.get(
        "GIPERION_SEQ2SEQ_OUTPUT",
        str(CHECKPOINT_FILE),
    )
)

BATCH_SIZE = 64
EPOCHS = 30
LEARNING_RATE = 1e-3
MAX_SRC_LEN = 32
MAX_TGT_LEN = 40
TEACHER_FORCING = 0.5
GRADIENT_CLIP = 1.0
TRAIN_SHARE = 0.9
EVAL_LIMIT = 300
SEED = 42

DEVICE = resolve_device()


def parameter_count(model) -> int:
    """Число обучаемых параметров модели."""

    return sum(
        parameter.numel()
        for parameter in model.parameters()
        if parameter.requires_grad
    )


class PairDataset(Dataset):
    """Пары «вопрос → ответ» в виде тензоров фиксированной длины."""

    def __init__(
        self,
        pairs: list[dict],
        tokenizer: WordTokenizer,
    ) -> None:
        self.samples = []
        self.tokenizer = tokenizer

        for pair in pairs:
            source = tokenizer.encode(
                pair["input"],
            )[:MAX_SRC_LEN]

            target = tokenizer.encode(
                pair["output"],
                add_sos=True,
                add_eos=True,
            )[:MAX_TGT_LEN]

            if not source or len(target) < 3:
                continue

            source = source + [tokenizer.pad_id] * (
                MAX_SRC_LEN - len(source)
            )

            target = target + [tokenizer.pad_id] * (
                MAX_TGT_LEN - len(target)
            )

            self.samples.append(
                {
                    "src": torch.tensor(
                        source,
                        dtype=torch.long,
                    ),
                    "tgt": torch.tensor(
                        target,
                        dtype=torch.long,
                    ),
                    "input": pair["input"],
                    "output": pair["output"],
                }
            )

    def __len__(self) -> int:
        """Число пар."""

        return len(self.samples)

    def __getitem__(
        self,
        index: int,
    ) -> dict:
        """Возвращает один подготовленный пример."""

        return self.samples[index]


class _SampleList(Dataset):
    """Готовый список примеров для DataLoader."""

    def __init__(self, samples: list[dict]) -> None:
        self.samples = samples

    def __len__(self) -> int:
        """Число примеров."""

        return len(self.samples)

    def __getitem__(self, index: int) -> dict:
        """Возвращает один пример."""

        return self.samples[index]


def one_response_per_input(
    pairs: list[dict],
) -> list[dict]:
    """Оставляет один случайный ответ на каждый вопрос."""

    grouped: dict[str, list[dict]] = {}

    for pair in pairs:
        grouped.setdefault(pair["input"], []).append(pair)

    rng = random.Random(SEED)

    return [
        rng.choice(options)
        for _key, options in sorted(grouped.items())
    ]


def split_samples(
    samples: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Перемешивает и делит на обучение и проверку."""

    shuffled = list(samples)
    random.Random(SEED).shuffle(shuffled)

    split_index = int(len(shuffled) * TRAIN_SHARE)

    return shuffled[:split_index], shuffled[split_index:]


def sequence_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    pad_id: int,
) -> torch.Tensor:
    """Средняя ошибка по словам ответа, паддинг не считается."""

    return F.cross_entropy(
        logits.reshape(-1, logits.size(-1)),
        target[:, 1:].reshape(-1),
        ignore_index=pad_id,
    )


def token_accuracy(
    logits: torch.Tensor,
    target: torch.Tensor,
    pad_id: int,
) -> float:
    """Доля верно предсказанных слов при подсказке учителя."""

    predictions = logits.argmax(dim=2)
    expected = target[:, 1:]

    mask = expected != pad_id
    correct = (predictions == expected) & mask

    return (
        correct.sum().item()
        / max(mask.sum().item(), 1)
    )


def ids_to_text(
    tokenizer: WordTokenizer,
    ids: list[int],
) -> str:
    """Собирает текст, обрывая его на первом </eos>."""

    cut = []

    for index in ids:
        if index == tokenizer.eos_id:
            break

        cut.append(index)

    return tokenizer.decode(cut)


def generation_score(
    model: Seq2Seq,
    samples: list[dict],
    tokenizer: WordTokenizer,
) -> float:
    """Доля ответов, совпавших с эталоном слово в слово."""

    if not samples:
        return 0.0

    model.eval()

    sources = torch.stack(
        [sample["src"] for sample in samples]
    ).to(DEVICE)

    source_mask = sources == tokenizer.pad_id

    with torch.no_grad():
        generated = model.generate(
            sources,
            source_mask,
            max_len=MAX_TGT_LEN,
        )

    exact = 0

    for sample, ids in zip(samples, generated, strict=False):
        text = ids_to_text(tokenizer, ids.tolist())

        reference = tokenizer.decode(
            tokenizer.encode(sample["output"])
        )

        exact += int(text == reference)

    return exact / len(samples)


def save_checkpoint(
    model: Seq2Seq,
) -> None:
    """Сохраняет веса модели и её настройки."""

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    save_torch(
        OUTPUT_FILE,
        {
            "format_version": 1,
            "model_state": model.state_dict(),
            "embed_dim": model.encoder_embedding.embedding_dim,
            "hidden_size": model.decoder_gru.hidden_size,
            "max_src_len": MAX_SRC_LEN,
            "max_tgt_len": MAX_TGT_LEN,
        },
    )


def print_examples(
    model: Seq2Seq,
    samples: list[dict],
    tokenizer: WordTokenizer,
    limit: int = 8,
) -> None:
    """Показывает пары «вопрос — эталон — ответ модели»."""

    model.eval()

    selected = samples[:limit]

    sources = torch.stack(
        [sample["src"] for sample in selected]
    ).to(DEVICE)

    source_mask = sources == tokenizer.pad_id

    with torch.no_grad():
        generated = model.generate(
            sources,
            source_mask,
            max_len=MAX_TGT_LEN,
        )

    for sample, ids in zip(selected, generated, strict=False):
        answer = ids_to_text(tokenizer, ids.tolist())

        print(f"Вопрос:  {sample['input']}")
        print(f"Эталон:  {sample['output']}")
        print(f"Модель:  {answer or '...'}")
        print()


def train() -> None:
    """Обучает генеративную модель и показывает примеры."""

    torch.manual_seed(SEED)

    with PAIRS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        pairs = json.load(file)

    if os.environ.get("GIPERION_SEQ2SEQ_ONE_RESPONSE") == "1":
        pairs = one_response_per_input(pairs)

    tokenizer = WordTokenizer.load(TOKENIZER_FILE)

    full_dataset = PairDataset(pairs, tokenizer)

    train_samples, val_samples = split_samples(
        full_dataset.samples
    )

    train_loader = DataLoader(
        _SampleList(train_samples),
        batch_size=BATCH_SIZE,
        shuffle=True,
        pin_memory=True,
    )

    eval_samples = val_samples[:EVAL_LIMIT]

    model = Seq2Seq(
        vocab_size=tokenizer.vocab_size,
        pad_id=tokenizer.pad_id,
        sos_id=tokenizer.sos_id,
        eos_id=tokenizer.eos_id,
    ).to(DEVICE)

    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=LEARNING_RATE,
    )

    print("=== Обучение генеративной модели Giperion ===")
    print(f"Устройство: {DEVICE}")
    if DEVICE.type == "cuda":
        print(f"Видеокарта: {torch.cuda.get_device_name(0)}")
    print(f"Пар для обучения: {len(train_samples)}")
    print(f"Пар для проверки: {len(val_samples)}")
    print(f"Параметров модели: {parameter_count(model)}")
    print()

    best_score = -1.0

    for epoch in range(1, EPOCHS + 1):
        model.train()
        epoch_loss = 0.0
        seen = 0
        accuracy_sum = 0.0
        batches = 0

        for batch in train_loader:
            source = batch["src"].to(DEVICE)
            target = batch["tgt"].to(DEVICE)

            source_mask = source == tokenizer.pad_id

            optimizer.zero_grad()

            logits = model(
                source,
                source_mask,
                target,
                teacher_forcing_ratio=TEACHER_FORCING,
            )

            loss = sequence_loss(
                logits,
                target,
                tokenizer.pad_id,
            )

            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                GRADIENT_CLIP,
            )

            optimizer.step()

            epoch_loss += loss.item() * target.size(0)
            seen += target.size(0)

            accuracy_sum += token_accuracy(
                logits,
                target,
                tokenizer.pad_id,
            )
            batches += 1

        score = generation_score(
            model,
            eval_samples,
            tokenizer,
        )

        if score >= best_score:
            best_score = score
            save_checkpoint(model)

        print(
            f"Эпоха {epoch:02d}/{EPOCHS}: "
            f"loss={epoch_loss / max(seen, 1):.4f} "
            f"tokens={accuracy_sum / max(batches, 1):.3f} "
            f"точный ответ={score:.3f}"
        )

    print()
    print(f"Лучшая точность генерации: {best_score:.3f}")
    print(f"Модель сохранена: {OUTPUT_FILE}")
    print()

    # Примеры должны показывать именно ту модель, которая сохранена.
    best_checkpoint = torch.load(
        OUTPUT_FILE,
        map_location=DEVICE,
        weights_only=True,
    )
    model.load_state_dict(best_checkpoint["model_state"])

    print_examples(
        model,
        val_samples,
        tokenizer,
    )


if __name__ == "__main__":
    train()
