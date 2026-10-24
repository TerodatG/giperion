# Giperion/app/memory/unknown_messages_handler.py                 v001
# Просмотр и очистка списка непонятых фраз Giperion.
# Последнее изменение: файл перемещён в пакет memory и обновлены импорты.

from giperion.language.intent_handler import find_intent_response
from terminal.memory.memory import (
    get_unknown_messages,
    remove_unknown_messages,
)


def get_unknown_messages_response() -> str:
    """Возвращает список непонятых фраз."""

    unknown_messages = get_unknown_messages()

    if not unknown_messages:
        return "Непонятых фраз пока нет."

    lines = ["Непонятые фразы:"]

    for number, message in enumerate(unknown_messages, start=1):
        lines.append(f"{number}. {message['text']}")

    return "\n".join(lines)


def clean_learned_unknown_messages() -> str:
    """Удаляет непонятые фразы, для которых уже найден ответ."""

    unknown_messages = get_unknown_messages()
    learned_texts = []

    for message in unknown_messages:
        text = message.get("text", "")

        if find_intent_response(text):
            learned_texts.append(text)

    if not learned_texts:
        return "Освоенных фраз для очистки не найдено."

    remove_unknown_messages(learned_texts)

    return (
        "Из списка непонятых удалено освоенных фраз: "
        f"{len(learned_texts)}."
    )
