# Giperion/tests/test_eval_generation.py                              v001
# Метрики оценки генератора ответов.
# Последнее изменение: первый вариант — кандидаты и согласованность.

from giperion_model.neural_engine import NeuralEngine
from tools.eval_generation import evaluate


def test_generation_metrics_count_consistency() -> None:
    """Считаются только ответы выше порога и совпавшие с темой."""

    engine = object.__new__(NeuralEngine)
    engine.classify = lambda text: ("greeting", 0.9)
    engine.generate = lambda text: "привет, друг"
    engine._matches_intent = lambda answer, label: label == "greeting"

    metrics = evaluate(
        engine,
        [
            {"text": "привет", "label": "greeting"},
            {"text": "шутка", "label": "joke"},
        ],
    )

    assert metrics["candidates"] == 2
    assert metrics["generated"] == 2
    assert metrics["consistent"] == 1
    assert metrics["generation_rate"] == 1.0
    assert metrics["consistency"] == 0.5


def test_generation_metrics_skip_low_confidence() -> None:
    """Ниже порога генерации кандидатов нет."""

    engine = object.__new__(NeuralEngine)
    engine.classify = lambda text: ("greeting", 0.1)
    engine.generate = lambda text: "привет"
    engine._matches_intent = lambda answer, label: True

    metrics = evaluate(
        engine,
        [{"text": "привет", "label": "greeting"}],
    )

    assert metrics["candidates"] == 0
    assert metrics["generation_rate"] == 0.0
    assert metrics["consistency"] == 0.0
