# Giperion/app/memory/memory.py                                   v003
# Постоянная память профиля, диалогов и непонятых фраз.
# Последнее изменение: JSON читается и пишется через app/storage/json_store.

from datetime import datetime

from shared.storage.json_store import read_json, write_json
from config import (
    CONVERSATIONS_FILE,
    UNKNOWN_MESSAGES_FILE,
    USER_PROFILE_FILE,
)

DEFAULT_USER_PROFILE = {
    "name": None,
}


def get_user_profile() -> dict:
    """Возвращает профиль пользователя."""

    profile = read_json(USER_PROFILE_FILE, None)

    if isinstance(profile, dict):
        return profile

    return DEFAULT_USER_PROFILE.copy()


def get_user_name() -> str | None:
    """Возвращает сохранённое имя пользователя."""

    profile = get_user_profile()
    name = profile.get("name")

    if isinstance(name, str) and name:
        return name

    return None


def set_user_name(name: str) -> None:
    """Сохраняет имя пользователя в профиль."""

    profile = get_user_profile()
    profile["name"] = name

    write_json(USER_PROFILE_FILE, profile)


def reset_user_profile() -> None:
    """Очищает профиль пользователя, сохраняя JSON-файл."""

    write_json(USER_PROFILE_FILE, DEFAULT_USER_PROFILE)


def get_conversations() -> list[dict]:
    """Возвращает сохранённую историю диалогов."""

    conversations = read_json(CONVERSATIONS_FILE, [])

    if isinstance(conversations, list):
        return conversations

    return []


def add_message(
    role: str,
    text: str,
    model: str | None = None,
) -> None:
    """Добавляет одно сообщение в историю диалогов.

    model — идентификатор модели, которая дала ответ. Нужен, чтобы
    обучение не принимало ответы внешних моделей за речь Гипериона.
    """

    conversations = get_conversations()

    record = {
        "role": role,
        "text": text,
        "created_at": datetime.now().isoformat(
            timespec="seconds",
        ),
    }

    if model and role == "assistant":
        record["model"] = model

    conversations.append(record)

    write_json(CONVERSATIONS_FILE, conversations)


def get_messages_count() -> int:
    """Возвращает количество сохранённых сообщений в истории."""

    return len(get_conversations())


def clear_conversations() -> None:
    """Очищает историю диалогов, сохраняя JSON-файл."""

    write_json(CONVERSATIONS_FILE, [])


def get_unknown_messages() -> list[dict]:
    """Возвращает список непонятых сообщений."""

    unknown_messages = read_json(UNKNOWN_MESSAGES_FILE, [])

    if isinstance(unknown_messages, list):
        return unknown_messages

    return []


def add_unknown_message(text: str) -> None:
    """Добавляет уникальную непонятую фразу в постоянную память."""

    unknown_messages = get_unknown_messages()
    normalized_text = text.lower().strip()

    for message in unknown_messages:
        saved_text = message.get("text", "").lower().strip()

        if saved_text == normalized_text:
            return

    unknown_messages.append(
        {
            "text": text,
            "created_at": datetime.now().isoformat(
                timespec="seconds",
            ),
        }
    )

    write_json(UNKNOWN_MESSAGES_FILE, unknown_messages)


def remove_unknown_messages(texts: list[str]) -> None:
    """Удаляет непонятые фразы по переданным текстам."""

    normalized_texts = {
        text.lower().strip()
        for text in texts
    }

    unknown_messages = get_unknown_messages()

    remaining_messages = [
        message
        for message in unknown_messages
        if message.get("text", "").lower().strip()
        not in normalized_texts
    ]

    write_json(UNKNOWN_MESSAGES_FILE, remaining_messages)


def clear_unknown_messages() -> None:
    """Очищает список непонятых фраз, сохраняя JSON-файл."""

    write_json(UNKNOWN_MESSAGES_FILE, [])


def reset_core_memory() -> None:
    """Сбрасывает профиль, историю и непонятые фразы без удаления файлов."""

    reset_user_profile()
    clear_conversations()
    clear_unknown_messages()