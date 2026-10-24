# Giperion/tests/test_model_api.py                                  v001
# Точка входа модели: намерение, нейросеть и честное «не знаю».

from giperion import api


def test_intent_answer_has_full_confidence(monkeypatch) -> None:
    """Точный ответ из intents.json — источник intent."""

    monkeypatch.setattr(
        api,
        "find_intent_response",
        lambda text: "Привет!",
    )

    reply = api.match_intent("привет")

    assert reply is not None
    assert reply.text == "Привет!"
    assert reply.source == "intent"
    assert reply.confidence == 1.0


def test_neural_answer_keeps_confidence(monkeypatch) -> None:
    """Нейросетевой ответ приходит с уверенностью модели."""

    monkeypatch.setattr(
        api.neural_engine,
        "get_neural_reply",
        lambda text: ("Сгенерированный ответ", 0.72),
    )

    reply = api.generate("расскажи что-нибудь")

    assert reply is not None
    assert reply.text == "Сгенерированный ответ"
    assert reply.source == "neural"
    assert reply.confidence == 0.72


def test_answer_prefers_intent(monkeypatch) -> None:
    """Правила важнее нейросети: точное знание идёт первым."""

    monkeypatch.setattr(
        api,
        "find_intent_response",
        lambda text: "Точный ответ",
    )
    monkeypatch.setattr(
        api.neural_engine,
        "get_neural_reply",
        lambda text: ("Нейросетевой", 0.9),
    )

    reply = api.answer("привет")

    assert reply is not None
    assert reply.text == "Точный ответ"
    assert reply.source == "intent"


def test_answer_returns_none_when_model_silent(monkeypatch) -> None:
    """Если ни правила, ни сеть не ответили — None, решает агент."""

    monkeypatch.setattr(
        api,
        "find_intent_response",
        lambda text: None,
    )
    monkeypatch.setattr(
        api.neural_engine,
        "get_neural_reply",
        lambda text: None,
    )

    assert api.answer("неизвестно что") is None
