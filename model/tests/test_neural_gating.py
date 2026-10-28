# GiperionModel/tests/test_neural_gating.py                           v001
# Порог уверенности выбирается по модели, которая дала ответ.
# Последнее изменение: первый вариант — роутер и CNN раздельно.

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


def test_missing_router_uses_cnn_threshold() -> None:
    """Без роутера порог берётся из CNN-константы."""

    engine = make_engine(None)
    engine._classify_cnn = lambda text: ("joke", 0.44)

    assert engine._gated_classification("шутка") is None

    engine._classify_cnn = lambda text: ("joke", 0.46)

    assert engine._gated_classification("шутка") == ("joke", 0.46)


def test_router_answers_without_cnn() -> None:
    """Роутер отвечает, даже если CNN не загружена."""

    engine = make_engine(FakeRouter(("greeting", 0.8)))
    engine.classifier = None
    engine.word_tokenizer = None
    engine.char_tokenizer = None
    engine.generator = None

    assert engine.classify("привет") == ("greeting", 0.8)
    assert engine.generate("привет") is None
