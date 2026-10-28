# Giperion/tests/test_linear_intent_augmentation.py                   v001
# Тематическая аугментация не должна пересекаться с eval-набором.
# Последнее изменение: первый вариант — проверка шаблонов.

import json

from config import DATA_DIR
from kraper_model.language.intent_handler import load_intents
from kraper_model.language.intent_topics import (
    INTENT_TOPICS,
    TOPIC_AUGMENT_TEMPLATES,
)
from shared.text_tools import normalize_message
from tools.train_linear_intent import augment_topics


def test_augmentation_tags_are_known() -> None:
    """Все темы ссылаются на существующие намерения."""

    tags = {
        intent["tag"] for intent in load_intents()
    }

    assert set(INTENT_TOPICS) <= tags


def test_augmentation_does_not_leak_into_eval() -> None:
    """Синтетические фразы не должны совпадать с проверочными."""

    texts, labels = augment_topics([], [])
    synthetic = {
        normalize_message(text)
        for text, label in zip(texts, labels, strict=False)
    }
    document = json.loads(
        (DATA_DIR / "eval_set.json").read_text(encoding="utf-8")
    )
    evaluation = {
        normalize_message(item["text"])
        for item in document["phrases"]
    }

    assert not synthetic & evaluation
    assert len(texts) == len(INTENT_TOPICS) * len(
        TOPIC_AUGMENT_TEMPLATES
    )
