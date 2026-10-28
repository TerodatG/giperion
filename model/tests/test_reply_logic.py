# GiperionModel/tests/test_reply_logic.py                             v001
# Ответы движка: генерация, пороги и шаблонные ответы.
# Последнее изменение: первый вариант — генератор и ответы без моделей.

import torch

from giperion_model.neural_engine import NeuralEngine


class FakeTokenizer:
    """Минимальный токенизатор для проверки путей движка."""

    pad_id = 0
    sos_id = 2
    eos_id = 3

    def __init__(self, decoded: str = "нормальный ответ") -> None:
        self.decoded = decoded

    def encode(self, text):
        return [4, 5]

    def decode(self, ids):
        return self.decoded


class FakeGenerator:
    """Генератор, возвращающий заранее заданные id."""

    def __init__(self, tokens) -> None:
        self.tokens = tokens

    def generate(
        self,
        source,
        source_mask,
        max_len,
        no_repeat_ngram_size=0,
    ):
        return torch.tensor([self.tokens])


def make_engine(decoded: str, tokens) -> NeuralEngine:
    """Собирает движок с фейковым генератором."""

    engine = object.__new__(NeuralEngine)
    engine.generator = FakeGenerator(tokens)
    engine.word_tokenizer = FakeTokenizer(decoded)
    engine.router = None
    engine.device = torch.device("cpu")
    engine.max_src_len = 2
    engine.max_tgt_len = 10

    return engine


def test_generate_decodes_tokens_until_eos() -> None:
    """EOS обрезает ответ, а нормальный текст проходит."""

    engine = make_engine("нормальный ответ", [4, 5, 3, 6])

    assert engine.generate("привет") == "нормальный ответ"


def test_generate_rejects_short_and_long_answers() -> None:
    """Слишком короткий и слишком длинный ответ не принимаются."""

    assert make_engine("ок", [4, 3]).generate("привет") is None
    assert (
        make_engine("я" * 300, [4, 3]).generate("привет") is None
    )


def test_generate_rejects_repetition() -> None:
    """Зацикленный текст отбрасывается после декодирования."""

    engine = make_engine(
        "привет как дела привет как дела",
        [4, 5, 3],
    )

    assert engine.generate("привет") is None


def test_generate_without_generator() -> None:
    """Без seq2seq генерация просто недоступна."""

    engine = make_engine("ответ", [4, 3])
    engine.generator = None

    assert engine.generate("привет") is None


def test_classify_without_router() -> None:
    """Без роутера классификатор возвращает пустой результат."""

    engine = make_engine("ответ", [4, 3])

    assert engine.classify("привет") == ("", 0.0)
