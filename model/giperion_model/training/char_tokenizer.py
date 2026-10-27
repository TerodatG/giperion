# Giperion/training/char_tokenizer.py                               v001
# Символьный токенизатор: фраза → последовательность id символов.
# Последнее изменение: первый вариант — словарь символов корпуса.

import json
from pathlib import Path

from giperion_model._shared.text_tools import normalize_message
from giperion_model.config import MODELS_DIR

CHAR_TOKENIZER_FILE = MODELS_DIR / "char_tokenizer.json"

PAD_ID = 0
UNK_ID = 1
MAX_CHAR_LEN = 96


class CharTokenizer:
    """Кодирует текст посимвольно: «привет» → 6 чисел.

    Символьный уровень ловит то, что словесный пропускает:
    морфемы («обучение» ↔ «обучил»), опечатки («привет» ↔
    «привит»), знакомые корни внутри новых слов.
    """

    def __init__(self, symbols: list[str]) -> None:
        self.symbols = symbols
        self.symbol_to_id = {
            symbol: index
            for index, symbol in enumerate(symbols)
        }

    @property
    def vocab_size(self) -> int:
        """Сколько символов в словаре (с спецсимволами)."""

        return len(self.symbols)

    @property
    def pad_id(self) -> int:
        """Id паддинга."""

        return PAD_ID

    @classmethod
    def fit(cls, texts: list[str]) -> "CharTokenizer":
        """Собирает словарь символов из корпуса."""

        found: set[str] = set()

        for text in texts:
            found.update(normalize_message(text))

        # Спецсимволы: <pad>=0, <unk>=1, затем — все символы.
        symbols = ["<pad>", "<unk>"] + sorted(found)

        return cls(symbols)

    def encode(
        self,
        text: str,
        max_len: int = MAX_CHAR_LEN,
    ) -> list[int]:
        """Кодирует текст: обрезает длинный, дополняет пустой."""

        normalized = normalize_message(text)

        ids = [
            self.symbol_to_id.get(char, UNK_ID)
            for char in normalized
        ]

        ids = ids[:max_len]
        ids = ids + [PAD_ID] * (max_len - len(ids))

        return ids

    @classmethod
    def load(
        cls,
        path: Path = CHAR_TOKENIZER_FILE,
    ) -> "CharTokenizer":
        """Загружает словарь из файла."""

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return cls(data["symbols"])

    def save(
        self,
        path: Path = CHAR_TOKENIZER_FILE,
    ) -> None:
        """Сохраняет словарь в файл."""

        path.parent.mkdir(parents=True, exist_ok=True)

        from giperion_model.storage import save_json

        save_json(path, {"symbols": self.symbols})


def build_corpus_texts() -> list[str]:
    """Собирает все тексты корпуса: фразы и пары диалога."""

    from giperion_model.training.build_dataset import (
        CLASSIFICATION_FILE,
        PAIRS_FILE,
    )

    texts = []

    with CLASSIFICATION_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        texts += [item["text"] for item in json.load(file)]

    with PAIRS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
        pairs = json.load(file)

    texts += [pair["input"] for pair in pairs]
    texts += [pair["output"] for pair in pairs]

    return texts


def main() -> None:
    """Собирает символьный словарь и сохраняет его."""

    texts = build_corpus_texts()
    tokenizer = CharTokenizer.fit(texts)
    tokenizer.save()

    print("=== Символьный токенизатор Giperion ===")
    print(f"Текстов в корпусе: {len(texts)}")
    print(f"Символов в словаре: {tokenizer.vocab_size}")
    print(f"Сохранён: {CHAR_TOKENIZER_FILE}")


if __name__ == "__main__":
    main()
