# GiperionModel/tests/test_generation_guards.py                       v001
# Защита от зацикленного и нерелевантного вывода seq2seq.
# Последнее изменение: первый вариант — повторы и обратная проверка.

from giperion_model.neural_engine import NeuralEngine, has_repetition


def test_repetition_detects_loops() -> None:
    """Повторяющийся триграмм — признак зацикливания."""

    assert has_repetition(
        "привет как дела привет как дела"
    )
    assert not has_repetition("привет! рад тебя видеть")
    assert not has_repetition("коротко")
    assert not has_repetition("")


def test_answer_must_match_intent() -> None:
    """Ответ другого намерения отбрасывается, неуверенный — принимается."""

    engine = object.__new__(NeuralEngine)
    engine.classify = lambda text: ("greeting", 0.9)

    assert engine._matches_intent("привет", "greeting")
    assert not engine._matches_intent("привет", "joke")

    engine.classify = lambda text: ("joke", 0.2)

    assert engine._matches_intent("привет", "greeting")
