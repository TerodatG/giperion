# Giperion/app/language/learning_commands.py                      v001
# Разбор и выполнение команд обучения и управления категориями.
# Последнее изменение: выделено из learning_handler.

import re
from typing import Callable

from giperion_model._shared.action_log import add_action
from giperion_model._shared.text_tools import normalize_message
from giperion_model.language.knowledge_service import (
    get_category_details,
    validate_answer_change,
    validate_category_removal,
    validate_phrase_removal,
)
from giperion_model.language.learning_presenter import get_categories_response
from giperion_model.language.learning_service import (
    add_phrase_to_category,
    get_available_categories,
    validate_new_category,
)

TEACH_PHRASE_PATTERN = re.compile(
    r"^научи фразе:\s*(.+?)\s*;\s*"
    r"категория:\s*(.+?)\s*$",
    re.IGNORECASE,
)

CREATE_CATEGORY_PATTERN = re.compile(
    r"^создай категорию:\s*(.+?)\s*;\s*"
    r"фраза:\s*(.+?)\s*;\s*"
    r"ответ:\s*(.+?)\s*$",
    re.IGNORECASE,
)

SHOW_CATEGORY_PATTERN = re.compile(
    r"^покажи фразы категории\s+(\S+)\s*$",
    re.IGNORECASE,
)

CHANGE_ANSWER_PATTERN = re.compile(
    r"^измени ответ категории\s+(\S+)\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)

REMOVE_PHRASE_PATTERN = re.compile(
    r"^удали фразу из категории\s+(\S+)\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)

REMOVE_CATEGORY_PATTERN = re.compile(
    r"^удали категорию\s+(\S+)\s*$",
    re.IGNORECASE,
)

SHOW_CATEGORIES_COMMANDS = {
    "покажи категории",
    "список категорий",
}

# Куда команда обучения отдаёт ожидающее действие. Модель не знает,
# как агент хранит состояние диалога: она только сообщает о намерении.
PendingAction = Callable[..., None]


def _stage(
    pending: PendingAction | None,
    action: str,
    **params: str,
) -> None:
    """Передаёт ожидающее действие агенту, если он его ждёт."""

    if pending is not None:
        pending(action, **params)


def _show_categories(message: str) -> str | None:
    """Показывает список категорий."""

    if message not in SHOW_CATEGORIES_COMMANDS:
        return None

    try:
        categories = get_available_categories()
    except (OSError, ValueError):
        return "Не удалось прочитать категории из intents.json."

    if not categories:
        return "В intents.json пока нет категорий."

    return get_categories_response(categories)


def _show_category(message: str) -> str | None:
    """Показывает фразы одной категории."""

    match = SHOW_CATEGORY_PATTERN.fullmatch(message)

    if not match:
        return None

    try:
        return get_category_details(match.group(1))
    except (OSError, ValueError):
        return (
            "Не удалось прочитать категорию. "
            "Проверь файл intents.json."
        )


def _create_category(
    message: str,
    pending: PendingAction | None,
) -> str | None:
    """Готовит создание категории."""

    match = CREATE_CATEGORY_PATTERN.fullmatch(message)

    if not match:
        return None

    category = match.group(1).strip()
    phrase = " ".join(match.group(2).split())
    response = " ".join(match.group(3).split())

    try:
        error = validate_new_category(category, phrase, response)
    except (OSError, ValueError):
        return (
            "Не удалось проверить данные. "
            "Проверь файл intents.json."
        )

    if error:
        return error

    _stage(
        pending,
        "create_category",
        category=category,
        phrase=phrase,
        response=response,
    )

    return (
        f"Будет создана категория «{category}» "
        f"с фразой «{phrase}» и ответом «{response}». "
        "Для выполнения напиши: подтверждаю. "
        "Для отмены напиши: отмена."
    )


def _change_answer(
    message: str,
    pending: PendingAction | None,
) -> str | None:
    """Готовит замену первого ответа категории."""

    match = CHANGE_ANSWER_PATTERN.fullmatch(message)

    if not match:
        return None

    category = match.group(1)
    response = " ".join(match.group(2).split())

    try:
        error = validate_answer_change(category, response)
    except (OSError, ValueError):
        return (
            "Не удалось проверить категорию. "
            "Проверь файл intents.json."
        )

    if error:
        return error

    _stage(
        pending,
        "change_category_answer",
        category=category,
        response=response,
    )

    return (
        f"Первый ответ категории «{category}» "
        f"будет заменён на «{response}». "
        "Для выполнения напиши: подтверждаю. "
        "Для отмены напиши: отмена."
    )


def _remove_phrase(
    message: str,
    pending: PendingAction | None,
) -> str | None:
    """Готовит удаление фразы из категории."""

    match = REMOVE_PHRASE_PATTERN.fullmatch(message)

    if not match:
        return None

    category = match.group(1)
    phrase = " ".join(match.group(2).split())

    try:
        error = validate_phrase_removal(category, phrase)
    except (OSError, ValueError):
        return (
            "Не удалось проверить фразу. "
            "Проверь файл intents.json."
        )

    if error:
        return error

    _stage(
        pending,
        "remove_category_phrase",
        category=category,
        phrase=phrase,
    )

    return (
        f"Фраза «{phrase}» будет удалена "
        f"из категории «{category}». "
        "Для выполнения напиши: подтверждаю. "
        "Для отмены напиши: отмена."
    )


def _remove_category(
    message: str,
    pending: PendingAction | None,
) -> str | None:
    """Готовит удаление категории целиком."""

    match = REMOVE_CATEGORY_PATTERN.fullmatch(message)

    if not match:
        return None

    category = match.group(1)

    try:
        error = validate_category_removal(category)
    except (OSError, ValueError):
        return (
            "Не удалось проверить категорию. "
            "Проверь файл intents.json."
        )

    if error:
        return error

    _stage(pending, "remove_category", category=category)

    return (
        f"Категория «{category}» и все её фразы "
        "и ответы будут удалены. "
        "Для выполнения напиши: подтверждаю. "
        "Для отмены напиши: отмена."
    )


def _teach_phrase(message: str) -> str | None:
    """Добавляет готовую фразу в категорию."""

    match = TEACH_PHRASE_PATTERN.fullmatch(message)

    if not match:
        return None

    phrase = match.group(1)
    category = match.group(2)

    try:
        result = add_phrase_to_category(phrase, category)
    except (OSError, ValueError):
        return (
            "Не удалось сохранить фразу. "
            "Проверь файл intents.json."
        )

    if result.startswith("Фраза добавлена"):
        add_action(
            "Добавлена обучающая фраза "
            f"в категорию {category.strip()}"
        )

    return result


def get_learning_response(
    user_message: str,
    pending: PendingAction | None = None,
) -> str | None:
    """Обрабатывает команды обучения и управления категориями."""

    message = normalize_message(user_message)
    original_message = user_message.strip()

    handlers = (
        lambda: _show_categories(message),
        lambda: _show_category(original_message),
        lambda: _create_category(original_message, pending),
        lambda: _change_answer(original_message, pending),
        lambda: _remove_phrase(original_message, pending),
        lambda: _remove_category(original_message, pending),
        lambda: _teach_phrase(original_message),
    )

    for handler in handlers:
        result = handler()

        if result is not None:
            return result

    return None
