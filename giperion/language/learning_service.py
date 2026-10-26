# Giperion/app/language/learning_service.py                       v003
# Добавление новых фраз и категорий в обучающие данные Giperion.
# Последнее изменение: запись intents.json через общий атомарный слой.

import json
import re
import threading

from config import DATA_DIR
from shared.storage.json_store import write_json
from shared.text_tools import normalize_message

INTENTS_FILE = DATA_DIR / "intents.json"

# Обучение и правка знаний меняют один и тот же intents.json:
# проверка и запись должны идти одной операцией.
INTENTS_LOCK = threading.Lock()

CATEGORY_NAME_PATTERN = re.compile(
    r"^[a-zA-Z][a-zA-Z0-9_]*$"
)


def load_intents_document() -> tuple[object, list[dict]]:
    """Загружает намерения, сохраняя исходный формат JSON."""

    with INTENTS_FILE.open("r", encoding="utf-8") as file:
        document = json.load(file)

    if isinstance(document, list):
        intents = document
    elif (
        isinstance(document, dict)
        and isinstance(document.get("intents"), list)
    ):
        intents = document["intents"]
    else:
        raise ValueError(
            "Неподдерживаемый формат intents.json."
        )

    if not all(
        isinstance(intent, dict)
        for intent in intents
    ):
        raise ValueError(
            "В intents.json обнаружены неверные записи."
        )

    return document, intents


def save_intents_document(document: object) -> None:
    """Сохраняет JSON атомарно, с завершающим переводом строки."""

    write_json(
        INTENTS_FILE,
        document,
        trailing_newline=True,
    )


def get_available_categories() -> list[str]:
    """Возвращает названия категорий из intents.json."""

    _, intents = load_intents_document()
    categories = []

    for intent in intents:
        tag = intent.get("tag")

        if isinstance(tag, str) and tag.strip():
            categories.append(tag)

    return sorted(
        set(categories)
    )


def validate_new_category(
    category: str,
    phrase: str,
    response: str,
) -> str | None:
    """Проверяет возможность создания категории без записи файла."""

    clean_category = category.strip()
    clean_phrase = " ".join(phrase.split())
    clean_response = " ".join(response.split())

    if not CATEGORY_NAME_PATTERN.fullmatch(
        clean_category
    ):
        return (
            "Название категории должно начинаться "
            "с латинской буквы и содержать только "
            "латинские буквы, цифры и знак _. "
        ).strip()

    if not clean_phrase:
        return "Фраза для обучения не может быть пустой."

    if not clean_response:
        return "Ответ категории не может быть пустым."

    _, intents = load_intents_document()

    normalized_phrase = normalize_message(
        clean_phrase
    )

    for intent in intents:
        tag = intent.get("tag")

        if not isinstance(tag, str):
            raise ValueError(
                "В intents.json обнаружена категория "
                "без корректного названия."
            )

        if (
            tag.casefold()
            == clean_category.casefold()
        ):
            return (
                f"Категория «{tag}» уже существует."
            )

        patterns = intent.get("patterns")

        if not isinstance(patterns, list):
            raise ValueError(
                "В intents.json обнаружен неверный "
                "список patterns."
            )

        for existing_phrase in patterns:
            if not isinstance(
                existing_phrase,
                str,
            ):
                raise ValueError(
                    "В intents.json обнаружена "
                    "неверная фраза."
                )

            if (
                normalize_message(existing_phrase)
                == normalized_phrase
            ):
                return (
                    "Эта фраза уже есть в категории "
                    f"«{tag}»."
                )

    return None


def create_category(
    category: str,
    phrase: str,
    response: str,
) -> str:
    """Создаёт категорию после повторной проверки данных."""

    with INTENTS_LOCK:
        return _create_category_locked(
            category,
            phrase,
            response,
        )


def _create_category_locked(
    category: str,
    phrase: str,
    response: str,
) -> str:
    """Создаёт категорию; вызывающий уже держит блокировку файла."""

    validation_error = validate_new_category(
        category,
        phrase,
        response,
    )

    if validation_error:
        return validation_error

    document, intents = load_intents_document()

    clean_category = category.strip()
    clean_phrase = " ".join(phrase.split())
    clean_response = " ".join(response.split())

    intents.append(
        {
            "tag": clean_category,
            "patterns": [
                clean_phrase
            ],
            "responses": [
                clean_response
            ],
        }
    )

    save_intents_document(document)

    return (
        f"Категория «{clean_category}» создана."
    )


def add_phrase_to_category(
    phrase: str,
    category: str,
) -> str:
    """Добавляет фразу к существующей категории."""

    with INTENTS_LOCK:
        return _add_phrase_to_category_locked(
            phrase,
            category,
        )


def _add_phrase_to_category_locked(
    phrase: str,
    category: str,
) -> str:
    """Добавляет фразу; вызывающий уже держит блокировку файла."""

    clean_phrase = " ".join(phrase.split())
    clean_category = category.strip()

    if not clean_phrase:
        return (
            "Фраза для обучения "
            "не может быть пустой."
        )

    if not clean_category:
        return (
            "Укажи категорию намерения."
        )

    document, intents = load_intents_document()
    target_intent = None

    for intent in intents:
        tag = intent.get("tag")

        if (
            isinstance(tag, str)
            and tag.casefold()
            == clean_category.casefold()
        ):
            target_intent = intent
            break

    if target_intent is None:
        return (
            f"Категория «{clean_category}» "
            "не найдена. Напиши «покажи категории», "
            "чтобы увидеть доступные."
        )

    patterns = target_intent.get("patterns")
    responses = target_intent.get("responses")

    if (
        not isinstance(patterns, list)
        or not all(
            isinstance(item, str)
            for item in patterns
        )
        or not isinstance(responses, list)
        or not responses
        or not all(
            isinstance(item, str)
            for item in responses
        )
    ):
        raise ValueError(
            "Категория содержит неверные "
            "patterns или responses."
        )

    normalized_phrase = normalize_message(
        clean_phrase
    )

    for intent in intents:
        other_patterns = intent.get(
            "patterns"
        )

        if not isinstance(
            other_patterns,
            list,
        ):
            raise ValueError(
                "В intents.json обнаружен "
                "неверный список patterns."
            )

        for existing_phrase in other_patterns:
            if not isinstance(
                existing_phrase,
                str,
            ):
                raise ValueError(
                    "В intents.json обнаружена "
                    "неверная фраза."
                )

            if (
                normalize_message(
                    existing_phrase
                )
                == normalized_phrase
            ):
                existing_category = intent.get(
                    "tag",
                    "без названия",
                )

                return (
                    "Эта фраза уже есть "
                    "в категории "
                    f"«{existing_category}»."
                )

    patterns.append(
        clean_phrase
    )
    save_intents_document(
        document
    )

    return (
        "Фраза добавлена в категорию "
        f"«{target_intent['tag']}»."
    )
