# Giperion/app/language/intent_handler.py                         v002
# Поиск ответов по намерениям и похожим фразам Giperion.
# Последнее изменение: добавлено чтение категорий из объекта с ключом intents.

import json
from difflib import get_close_matches

from config import DATA_DIR
from shared.text_tools import normalize_message

INTENTS_FILE = DATA_DIR / "intents.json"


def load_intents() -> list[dict]:
    """Загружает намерения из списка или объекта с ключом intents."""

    if not INTENTS_FILE.exists():
        return []

    try:
        with INTENTS_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            document = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(document, list):
        intents = document
    elif isinstance(document, dict):
        intents = document.get("intents")
    else:
        return []

    if not isinstance(intents, list):
        return []

    return [
        intent
        for intent in intents
        if isinstance(intent, dict)
    ]


def find_intent_response(
    message: str,
) -> str | None:
    """Возвращает ответ для точного совпадения с известной фразой."""

    normalized_message = normalize_message(
        message
    )

    for intent in load_intents():
        patterns = intent.get(
            "patterns",
            [],
        )
        responses = intent.get(
            "responses",
            [],
        )

        if (
            not isinstance(patterns, list)
            or not isinstance(responses, list)
        ):
            continue

        normalized_patterns = [
            normalize_message(pattern)
            for pattern in patterns
            if isinstance(pattern, str)
        ]

        if (
            normalized_message in normalized_patterns
            and responses
            and isinstance(responses[0], str)
        ):
            return responses[0]

    return None


def find_close_pattern(
    message: str,
) -> str | None:
    """Ищет наиболее похожую известную фразу."""

    normalized_message = normalize_message(
        message
    )
    patterns = []

    for intent in load_intents():
        intent_patterns = intent.get(
            "patterns",
            [],
        )

        if isinstance(
            intent_patterns,
            list,
        ):
            patterns.extend(
                pattern
                for pattern in intent_patterns
                if isinstance(
                    pattern,
                    str,
                )
            )

    normalized_patterns = {
        normalize_message(pattern): pattern
        for pattern in patterns
    }

    close_matches = get_close_matches(
        normalized_message,
        normalized_patterns.keys(),
        n=1,
        cutoff=0.78,
    )

    if not close_matches:
        return None

    return normalized_patterns[
        close_matches[0]
    ]
