# Giperion/tests/test_eval_set.py                                    v004
# Инварианты отложенного набора: чистый, размеченный, без утечек.
# Последнее изменение: 20 natural и 10 template фраз на класс.

import json
from collections import Counter

from config import DATA_DIR
from giperion_model.language.intent_handler import load_intents
from shared.text_tools import normalize_message

EVAL_FILE = DATA_DIR / "eval_set.json"


def load_document() -> dict:
    """Читает отложенный набор целиком."""

    return json.loads(EVAL_FILE.read_text(encoding="utf-8"))


def load_phrases() -> list[dict]:
    """Возвращает список фраз отложенного набора."""

    return load_document()["phrases"]


def intent_tags() -> set[str]:
    """Собирает известные теги намерений."""

    tags = set()

    for intent in load_intents():
        tag = intent.get("tag")

        if isinstance(tag, str) and tag.strip():
            tags.add(tag)

    return tags


def training_patterns() -> set[str]:
    """Собирает нормализованные фразы, которые есть в обучении."""

    patterns = set()

    for intent in load_intents():
        for pattern in intent.get("patterns", []):
            if isinstance(pattern, str):
                patterns.add(normalize_message(pattern))

    return patterns


def test_eval_phrases_are_valid() -> None:
    """У каждой фразы есть текст и известный тег."""

    tags = intent_tags()

    for item in load_phrases():
        assert isinstance(item, dict)
        assert isinstance(item.get("text"), str)
        assert item["text"].strip()
        assert isinstance(item.get("label"), str)
        assert item["label"] in tags


def test_eval_set_has_no_internal_duplicates() -> None:
    """Одна и та же фраза не должна встречаться дважды."""

    texts = [
        normalize_message(item["text"])
        for item in load_phrases()
    ]
    duplicates = [
        text
        for text, count in Counter(texts).items()
        if count > 1
    ]

    assert not duplicates, (
        "Повторы в отложенном наборе:\n"
        + "\n".join(duplicates)
    )


def test_eval_set_is_disjoint_from_training() -> None:
    """Отложенные фразы не должны попадать в intents.json."""

    patterns = training_patterns()
    leaks = [
        item["text"]
        for item in load_phrases()
        if normalize_message(item["text"]) in patterns
    ]

    assert not leaks, (
        "Эти фразы уже есть в обучении:\n"
        + "\n".join(leaks)
    )


def test_eval_set_covers_every_intent() -> None:
    """У каждого намерения есть хотя бы тридцать отложенных фраз."""

    counts = Counter(
        item["label"] for item in load_phrases()
    )
    tags = intent_tags()

    assert not tags - set(counts), (
        "Нет отложенных фраз для: "
        + ", ".join(sorted(tags - set(counts)))
    )
    assert not set(counts) - tags, (
        "Неизвестные теги в наборе: "
        + ", ".join(sorted(set(counts) - tags))
    )

    thin = sorted(
        label
        for label, count in counts.items()
        if count < 30
    )

    assert not thin, (
        "Меньше тридцати фраз на класс: " + ", ".join(thin)
    )


def test_eval_set_has_two_balanced_subsets() -> None:
    """На каждый класс приходится 20 natural и 10 template фраз."""

    counts = Counter(
        (item["label"], item.get("source"))
        for item in load_phrases()
    )
    tags = intent_tags()

    assert {
        source
        for _label, source in counts
    } <= {"natural", "template"}

    for tag in tags:
        assert counts[(tag, "natural")] == 20
        assert counts[(tag, "template")] == 10


def test_eval_meta_matches_content() -> None:
    """Счётчики в _meta не должны расходиться с файлом."""

    document = load_document()
    meta = document.get("_meta", {})
    phrases = document["phrases"]

    if "total_phrases" in meta:
        assert meta["total_phrases"] == len(phrases)

    if "total_intents" in meta:
        assert meta["total_intents"] == len(
            {item["label"] for item in phrases}
        )
