# Giperion/app/language/knowledge_service.py                      v001
# Просмотр и изменение уже выученных категорий Giperion.
# Последнее изменение: добавлены просмотр, изменение ответа и удаление знаний.

from giperion.language.learning_service import (
    load_intents_document,
    save_intents_document,
)
from shared.text_tools import normalize_message


def find_category(
    intents: list[dict],
    category: str,
) -> dict | None:
    """Находит категорию без учёта регистра названия."""

    for intent in intents:
        tag = intent.get("tag")

        if (
            isinstance(tag, str)
            and tag.casefold() == category.strip().casefold()
        ):
            return intent

    return None


def get_category_details(category: str) -> str:
    """Возвращает фразы и ответы выбранной категории."""

    _, intents = load_intents_document()
    intent = find_category(intents, category)

    if intent is None:
        return f"Категория «{category}» не найдена."

    patterns = intent.get("patterns")
    responses = intent.get("responses")

    if (
        not isinstance(patterns, list)
        or not isinstance(responses, list)
        or not all(isinstance(item, str) for item in patterns)
        or not all(isinstance(item, str) for item in responses)
    ):
        raise ValueError(
            "Категория содержит неверные фразы или ответы."
        )

    lines = [
        f"Категория «{intent['tag']}»:",
        "Фразы:",
    ]

    if patterns:
        lines.extend(
            f"- {pattern}"
            for pattern in patterns
        )
    else:
        lines.append("- нет")

    lines.append("Ответы:")

    if responses:
        lines.extend(
            f"- {response}"
            for response in responses
        )
    else:
        lines.append("- нет")

    return "\n".join(lines)


def validate_answer_change(
    category: str,
    new_response: str,
) -> str | None:
    """Проверяет замену ответа без изменения файла."""

    if not new_response.strip():
        return "Новый ответ не может быть пустым."

    _, intents = load_intents_document()
    intent = find_category(intents, category)

    if intent is None:
        return f"Категория «{category}» не найдена."

    responses = intent.get("responses")

    if (
        not isinstance(responses, list)
        or not responses
        or not all(isinstance(item, str) for item in responses)
    ):
        raise ValueError(
            "Категория содержит неверный список ответов."
        )

    return None


def change_category_answer(
    category: str,
    new_response: str,
) -> str:
    """Заменяет первый ответ категории после повторной проверки."""

    error = validate_answer_change(
        category,
        new_response,
    )

    if error:
        return error

    document, intents = load_intents_document()
    intent = find_category(intents, category)

    if intent is None:
        return f"Категория «{category}» не найдена."

    intent["responses"][0] = " ".join(
        new_response.split()
    )

    save_intents_document(document)

    return (
        f"Ответ категории «{intent['tag']}» изменён."
    )


def find_phrase_index(
    patterns: list[str],
    phrase: str,
) -> int | None:
    """Находит фразу с учётом нормализации текста."""

    normalized_phrase = normalize_message(phrase)

    for index, pattern in enumerate(patterns):
        if normalize_message(pattern) == normalized_phrase:
            return index

    return None


def validate_phrase_removal(
    category: str,
    phrase: str,
) -> str | None:
    """Проверяет удаление фразы без изменения файла."""

    if not phrase.strip():
        return "Укажи фразу для удаления."

    _, intents = load_intents_document()
    intent = find_category(intents, category)

    if intent is None:
        return f"Категория «{category}» не найдена."

    patterns = intent.get("patterns")

    if (
        not isinstance(patterns, list)
        or not all(isinstance(item, str) for item in patterns)
    ):
        raise ValueError(
            "Категория содержит неверный список фраз."
        )

    if find_phrase_index(patterns, phrase) is None:
        return (
            f"Фраза не найдена в категории «{intent['tag']}»."
        )

    if len(patterns) == 1:
        return (
            "Нельзя удалить единственную фразу категории. "
            "Добавь другую фразу или удали категорию целиком."
        )

    return None


def remove_phrase(
    category: str,
    phrase: str,
) -> str:
    """Удаляет фразу после повторной проверки."""

    error = validate_phrase_removal(
        category,
        phrase,
    )

    if error:
        return error

    document, intents = load_intents_document()
    intent = find_category(intents, category)

    if intent is None:
        return f"Категория «{category}» не найдена."

    index = find_phrase_index(
        intent["patterns"],
        phrase,
    )

    if index is None:
        return (
            f"Фраза не найдена в категории «{intent['tag']}»."
        )

    del intent["patterns"][index]
    save_intents_document(document)

    return (
        f"Фраза удалена из категории «{intent['tag']}»."
    )


def validate_category_removal(
    category: str,
) -> str | None:
    """Проверяет существование категории перед удалением."""

    _, intents = load_intents_document()

    if find_category(intents, category) is None:
        return f"Категория «{category}» не найдена."

    return None


def remove_category(
    category: str,
) -> str:
    """Удаляет категорию после повторной проверки."""

    error = validate_category_removal(category)

    if error:
        return error

    document, intents = load_intents_document()
    intent = find_category(intents, category)

    if intent is None:
        return f"Категория «{category}» не найдена."

    actual_name = intent["tag"]
    intents.remove(intent)

    save_intents_document(document)

    return f"Категория «{actual_name}» удалена."
