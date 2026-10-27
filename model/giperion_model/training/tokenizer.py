# GiperionModel/giperion_model/training/tokenizer.py                  v002
# Свой словесный токенизатор Giperion: словарь, кодирование, декодирование.
# Последнее изменение: тире (— –) больше не приклеивается к слову при декодировании.

import json
import re
from collections import Counter
from pathlib import Path

from giperion_model._shared.text_tools import normalize_message
from giperion_model.config import MODELS_DIR
from giperion_model.training.build_dataset import (
    CLASSIFICATION_FILE,
    PAIRS_FILE,
)

TOKENIZER_FILE = MODELS_DIR / "tokenizer.json"

# Служебные токены. Их индексы всегда 0-3.
PAD_TOKEN = "<pad>"
UNK_TOKEN = "<unk>"
SOS_TOKEN = "<sos>"
EOS_TOKEN = "<eos>"

SPECIAL_TOKENS = (
    PAD_TOKEN,
    UNK_TOKEN,
    SOS_TOKEN,
    EOS_TOKEN,
)

# Слова (буквы и цифры) и одиночная пунктуация — раздельно.
TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]")

# Пунктуация, которую нужно приклеить к предыдущему слову.
# Тире (— –) исключено: в русском тексте оно стоит с пробелами.
PUNCTUATION_PATTERN = re.compile(
    r"\s+([^\w\s<>—–])"
)


def tokenize_text(text: str) -> list[str]:
    """Разбивает текст на слова и знаки пунктуации после нормализации."""

    normalized_text = normalize_message(text)

    return TOKEN_PATTERN.findall(normalized_text)


class WordTokenizer:
    """Словесный токенизатор со словарём частот."""

    def __init__(
        self,
        vocab: dict[str, int] | None = None,
    ) -> None:
        """Создаёт токенизатор; пустой — только со служебными токенами."""

        if vocab is None:
            vocab = {
                token: index
                for index, token in enumerate(SPECIAL_TOKENS)
            }

        self.vocab = vocab
        self.inverse = {
            index: token
            for token, index in vocab.items()
        }

        self.pad_id = vocab[PAD_TOKEN]
        self.unk_id = vocab[UNK_TOKEN]
        self.sos_id = vocab[SOS_TOKEN]
        self.eos_id = vocab[EOS_TOKEN]

    @property
    def vocab_size(self) -> int:
        """Число токенов в словаре."""

        return len(self.vocab)

    def fit(
        self,
        texts: list[str],
        min_freq: int = 1,
        max_size: int = 30000,
    ) -> int:
        """Наполняет словарь по частотам. Возвращает его размер."""

        counter: Counter[str] = Counter()

        for text in texts:
            counter.update(tokenize_text(text))

        items = sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        )

        for token, frequency in items:
            if frequency < min_freq:
                break

            if len(self.vocab) >= max_size:
                break

            if token in self.vocab:
                continue

            self.vocab[token] = len(self.vocab)

        self.inverse = {
            index: token
            for token, index in self.vocab.items()
        }

        return self.vocab_size

    def encode(
        self,
        text: str,
        add_sos: bool = False,
        add_eos: bool = False,
    ) -> list[int]:
        """Превращает текст в числа; неизвестные слова → <unk>."""

        ids = [
            self.vocab.get(token, self.unk_id)
            for token in tokenize_text(text)
        ]

        if add_sos:
            ids.insert(0, self.sos_id)

        if add_eos:
            ids.append(self.eos_id)

        return ids

    def decode(
        self,
        ids: list[int],
    ) -> str:
        """Собирает текст из чисел, скрывая служебные токены."""

        tokens = []

        for index in ids:
            token = self.inverse.get(int(index), UNK_TOKEN)

            if token in (PAD_TOKEN, SOS_TOKEN, EOS_TOKEN, UNK_TOKEN):
                continue

            tokens.append(token)

        text = " ".join(tokens)

        return PUNCTUATION_PATTERN.sub(r"\1", text)

    def save(
        self,
        path: Path = TOKENIZER_FILE,
    ) -> None:
        """Сохраняет словарь в JSON."""

        path.parent.mkdir(parents=True, exist_ok=True)

        from giperion_model.storage import save_json

        save_json(path, {"vocab": self.vocab})

    @classmethod
    def load(
        cls,
        path: Path = TOKENIZER_FILE,
    ) -> "WordTokenizer":
        """Загружает словарь из JSON."""

        with path.open("r", encoding="utf-8") as file:
            document = json.load(file)

        return cls(vocab=document["vocab"])


def load_corpus() -> list[str]:
    """Собирает все тексты датасета в один корпус."""

    texts = []

    classification = json.loads(
        CLASSIFICATION_FILE.read_text(encoding="utf-8")
    )
    pairs = json.loads(
        PAIRS_FILE.read_text(encoding="utf-8")
    )

    for example in classification:
        texts.append(example["text"])

    for pair in pairs:
        texts.append(pair["input"])
        texts.append(pair["output"])

    return texts


def demo() -> None:
    """Обучает токенизатор на датасете и показывает примеры."""

    corpus = load_corpus()

    tokenizer = WordTokenizer()
    vocab_size = tokenizer.fit(corpus)

    print("=== Токенизатор Giperion ===")
    print(f"Текстов в корпусе: {len(corpus)}")
    print(f"Размер словаря: {vocab_size}")
    print()

    examples = (
        "Привет! Как дела?",
        "который сечас час?",
        "2 плюс 3 = ?",
    )

    for text in examples:
        ids = tokenizer.encode(text, add_sos=True, add_eos=True)
        decoded = tokenizer.decode(ids)
        print(f"Текст:  {text}")
        print(f"IDs:    {ids}")
        print(f"Назад:  {decoded}")
        print()

    unknown_ids = tokenizer.encode("фыркачество гиперболоид")
    print(f"Неизвестные слова: {unknown_ids}")
    print(f"Назад: {tokenizer.decode(unknown_ids)}")

    tokenizer.save()
    print()
    print(f"Сохранено: {TOKENIZER_FILE}")


if __name__ == "__main__":
    demo()
