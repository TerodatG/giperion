# Giperion/giperion/api.py                                           v001
# Единственная точка входа модели: текст на входе, ответ на выходе.
# Последнее изменение: первый вариант — намерение и нейросетевой ответ.

from dataclasses import dataclass

from giperion_model import neural_engine
from giperion_model.language.intent_handler import find_intent_response


@dataclass(frozen=True)
class ModelReply:
    """Ответ модели: текст, источник и уверенность."""

    text: str
    source: str
    confidence: float


def match_intent(text: str) -> ModelReply | None:
    """Точный ответ из intents.json — уверенность полная."""

    answer = find_intent_response(text)

    if not answer:
        return None

    return ModelReply(
        text=answer,
        source="intent",
        confidence=1.0,
    )


def generate(text: str) -> ModelReply | None:
    """Нейросетевой ответ, если модель уверена."""

    result = neural_engine.get_neural_reply(text)

    if result is None:
        return None

    answer, confidence = result

    return ModelReply(
        text=answer,
        source="neural",
        confidence=confidence,
    )


def answer(text: str) -> ModelReply | None:
    """Ответ модели или None: сначала правила, затем нейросеть.

    Внешний мир (агент, тесты, стенд) должен звать только эту функцию,
    чтобы не зависеть от внутреннего устройства модели.
    """

    return match_intent(text) or generate(text)
