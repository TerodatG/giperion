# Giperion/app/memory/profile_handler.py                          v002
# Обработка фраз профиля и имени пользователя Giperion.
# Последнее изменение: восстановлено содержимое после случайной замены другим файлом.

import re

from terminal.core.phrases import PROFILE_QUESTIONS
from terminal.memory.memory import (
    get_user_name,
    set_user_name,
)

NAME_PATTERNS = [
    re.compile(
        r"^меня зовут\s+([а-яёa-z-]+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^моё имя\s+([а-яёa-z-]+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^мое имя\s+([а-яёa-z-]+)$",
        re.IGNORECASE,
    ),
    # «я — Влад» и «я, Влад» — явные формы. Общий шаблон «я устал»
    # запрещён: он превращал состояние в имя пользователя.
    re.compile(
        r"^я\s*[-,—]\s*([а-яёa-z-]+)$",
        re.IGNORECASE,
    ),
]


def format_name(name: str) -> str:
    """Приводит имя пользователя к аккуратному виду."""

    return name.strip().capitalize()


def get_name_from_message(message: str) -> str | None:
    """Пытается извлечь имя пользователя из сообщения."""

    for pattern in NAME_PATTERNS:
        match = pattern.fullmatch(message)

        if match:
            return format_name(match.group(1))

    return None


def get_name_response(message: str) -> str | None:
    """Обрабатывает сохранение и вывод имени пользователя."""

    user_name = get_name_from_message(message)

    if user_name:
        set_user_name(user_name)

        return f"Запомнил. Тебя зовут {user_name}."

    if any(
        question in message
        for question in PROFILE_QUESTIONS
    ):
        saved_name = get_user_name()

        if saved_name:
            return f"Тебя зовут {saved_name}."

        return (
            "Я пока не знаю твоё имя. "
            "Напиши: меня зовут Имя."
        )

    return None


def get_profile_response(message: str) -> str | None:
    """Возвращает ответ на дополнительные вопросы о профиле."""

    if "что ты помнишь обо мне" in message:
        saved_name = get_user_name()

        if saved_name:
            return f"Я помню, что тебя зовут {saved_name}."

        return "О тебе пока ничего не сохранено."

    return None
