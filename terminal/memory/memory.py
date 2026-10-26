# Giperion/app/memory/memory.py                                   v003
# Постоянная память профиля, диалогов и непонятых фраз.
# Последнее изменение: JSON читается и пишется через app/storage/json_store.

from datetime import datetime

from config import (
    CONVERSATIONS_FILE,
    UNKNOWN_MESSAGES_FILE,
    USER_PROFILE_FILE,
)
from shared.storage.json_store import read_json, update_json, write_json

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

    def mutate(document: object) -> dict:
        profile = document if isinstance(document, dict) else {}

        profile["name"] = name

        return profile

    update_json(
        USER_PROFILE_FILE,
        mutate,
        default=DEFAULT_USER_PROFILE.copy(),
    )


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

    record = {
        "role": role,
        "text": text,
        "created_at": datetime.now().isoformat(
            timespec="seconds",
        ),
    }

    if model and role == "assistant":
        record["model"] = model

    def mutate(document: object) -> list:
        conversations = document if isinstance(document, list) else []
        conversations.append(record)

        return conversations

    update_json(
        CONVERSATIONS_FILE,
        mutate,
        default=[],
    )


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

    normalized_text = text.lower().strip()

    def mutate(document: object) -> list:
        unknown_messages = (
            document if isinstance(document, list) else []
        )

        for message in unknown_messages:
            saved_text = str(message.get("text", "")).lower().strip()

            if saved_text == normalized_text:
                return unknown_messages

        unknown_messages.append(
            {
                "text": text,
                "created_at": datetime.now().isoformat(
                    timespec="seconds",
                ),
            }
        )

        return unknown_messages

    update_json(
        UNKNOWN_MESSAGES_FILE,
        mutate,
        default=[],
    )


def remove_unknown_messages(texts: list[str]) -> None:
    """Удаляет непонятые фразы по переданным текстам."""

    normalized_texts = {
        text.lower().strip()
        for text in texts
    }

    def mutate(document: object) -> list:
        unknown_messages = (
            document if isinstance(document, list) else []
        )

        return [
            message
            for message in unknown_messages
            if str(message.get("text", "")).lower().strip()
            not in normalized_texts
        ]

    update_json(
        UNKNOWN_MESSAGES_FILE,
        mutate,
        default=[],
    )


def clear_unknown_messages() -> None:
    """Очищает список непонятых фраз, сохраняя JSON-файл."""

    write_json(UNKNOWN_MESSAGES_FILE, [])


def reset_core_memory() -> None:
    """Сбрасывает профиль, историю и непонятые фразы без удаления файлов."""

    reset_user_profile()
    clear_conversations()
    clear_unknown_messages()