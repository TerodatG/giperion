# Giperion/tests/test_intent_taxonomy.py                              v001
# Пояснения к близким намерениям.
# Последнее изменение: первый вариант — проверка тегов и текстов.

from giperion_model.language.intent_handler import load_intents
from giperion_model.language.intent_taxonomy import TAXONOMY_NOTES


def test_taxonomy_pairs_reference_known_tags() -> None:
    """Все пары ссылаются на существующие намерения."""

    tags = {intent["tag"] for intent in load_intents()}

    for left, right in TAXONOMY_NOTES:
        assert left in tags
        assert right in tags
        assert left != right


def test_taxonomy_notes_are_explanatory() -> None:
    """Каждая пара объясняет различие, а не просто повторяет теги."""

    assert ("garden", "plants") in TAXONOMY_NOTES
    assert ("astronomy", "space") in TAXONOMY_NOTES

    for note in TAXONOMY_NOTES.values():
        assert isinstance(note, str)
        assert len(note) > 30
