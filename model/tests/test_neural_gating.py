# GiperionModel/tests/test_neural_gating.py                           v002
# Порог уверенности роутера и поведение без генератора.
# Последнее изменение: CNN удалена из рантайма.

from giperion_model.neural_engine import NeuralEngine


class FakeRouter:
    """Роутер с заранее заданным ответом."""

    threshold = 0.5

    def __init__(self, result) -> None:
        self.result = result

    def predict(self, text):
        return self.result


def make_engine(router) -> NeuralEngine:
    """Собирает движок без загрузки моделей."""

    engine = object.__new__(NeuralEngine)
    engine.router = router

    return engine


def test_router_below_threshold_abstains() -> None:
    """Слабый ответ роутера не проходит порог 0.50."""

    engine = make_engine(FakeRouter(("greeting", 0.49)))

    assert engine._gated_classification("привет") is None


def test_router_at_threshold_answers() -> None:
    """Ровно порог уже считается уверенным ответом."""

    engine = make_engine(FakeRouter(("greeting", 0.50)))

    assert engine._gated_classification("привет") == (
        "greeting",
        0.5,
    )


def test_missing_router_abstains() -> None:
    """Без роутера движок не угадывает намерение."""

    engine = make_engine(None)

    assert engine.classify("привет") == ("", 0.0)
    assert engine._gated_classification("привет") is None


def test_router_answers_without_generator() -> None:
    """Роутер отвечает, даже если seq2seq не загружен."""

    engine = make_engine(FakeRouter(("greeting", 0.8)))
    engine.generator = None
    engine.word_tokenizer = None
    engine.max_src_len = 0
    engine.max_tgt_len = 0

    assert engine.classify("привет") == ("greeting", 0.8)
    assert engine.generate("привет") is None
