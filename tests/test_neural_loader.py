# Giperion/tests/test_neural_loader.py                             v001
# Проверки загрузчика нейросети и сброса кэша моделей.

from giperion import neural_engine
from giperion.neural_loader import load_responses


def test_intent_responses_are_loaded() -> None:
    """Загрузчик собирает ответы по тегам намерений."""

    responses = load_responses()

    assert "greeting" in responses
    assert responses["greeting"]


def test_reload_engine_resets_cache(monkeypatch) -> None:
    """Сброс кэша заставляет загрузить модели заново."""

    monkeypatch.setattr(neural_engine, "_engine", object())
    monkeypatch.setattr(neural_engine, "_engine_checked", True)

    neural_engine.reload_engine()

    assert neural_engine._engine is None
    assert neural_engine._engine_checked is False
