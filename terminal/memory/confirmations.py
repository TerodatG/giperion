# Giperion/app/memory/confirmations.py                            v001
# Исполнение и отмена системных действий, ожидающих подтверждения.
# Последнее изменение: выделено из system_handler.

from giperion_model.language.knowledge_service import (
    change_category_answer,
    remove_category,
    remove_phrase,
)
from giperion_model.language.learning_service import create_category

from shared.action_log import add_action
from terminal.core.pending_state import (
    clear_pending_action,
    get_pending_action,
)
from terminal.core.phrases import (
    CANCEL_COMMANDS,
    CONFIRM_COMMANDS,
    NO_ANSWERS,
    YES_ANSWERS,
)
from terminal.memory.archive_service import (
    delete_archive,
    restore_archive,
)
from terminal.memory.memory import (
    clear_conversations,
    clear_unknown_messages,
    reset_core_memory,
)
from terminal.memory.system_commands import create_archive_response


def _create_archive_reply(message: str) -> str:
    """Реакция на подтверждение создания архива."""

    if message in YES_ANSWERS:
        clear_pending_action()

        return create_archive_response()

    if message in NO_ANSWERS:
        clear_pending_action()
        add_action("Отменено создание архива")

        return "Создание архива отменено."

    return (
        "Ответь «да», чтобы создать архив, "
        "или «нет», чтобы отменить."
    )


def _cancel_pending(
    action: str,
    archive_id,
    category,
) -> str:
    """Отменяет ожидающее действие и пишет журнал."""

    clear_pending_action()

    if archive_id:
        add_action(
            "Отменено действие "
            f"{action} для архива {archive_id}"
        )
    elif category:
        add_action(
            f"Отменено действие {action} "
            f"для категории {category}"
        )
    else:
        add_action(f"Отменено действие {action}")

    return "Операция отменена. Данные не изменены."


def _clear_reply(action: str) -> str | None:
    """Очистка памяти и истории."""

    if action == "clear_unknown_messages":
        clear_unknown_messages()
        add_action("Очищен список непонятых фраз")

        return "Список непонятых фраз очищен."

    if action == "clear_conversations":
        clear_conversations()
        add_action("Очищена история переписки")

        return "История переписки очищена."

    if action == "reset_core":
        reset_core_memory()
        add_action("Память ИИ-ядра полностью обнулена")

        return "Память ИИ-ядра полностью обнулена."

    return None


def _archive_reply(action: str, archive_id) -> str | None:
    """Восстановление и удаление архива."""

    if action == "restore_archive" and archive_id:
        if restore_archive(archive_id):
            add_action(
                "Восстановлена память "
                f"из архива {archive_id}"
            )

            return (
                "Память ИИ-ядра восстановлена. "
                f"Архив {archive_id}."
            )

        return f"Не удалось восстановить архив {archive_id}."

    if action == "delete_archive" and archive_id:
        if delete_archive(archive_id):
            add_action(f"Удалён архив {archive_id}")

            return f"Архив {archive_id} удалён."

        return f"Не удалось удалить архив {archive_id}."

    return None


def _create_category_reply(category, phrase, response) -> str:
    """Создаёт категорию."""

    try:
        result = create_category(category, phrase, response)
    except (OSError, ValueError):
        return (
            "Не удалось создать категорию. "
            "Проверь файл intents.json."
        )

    if result.endswith("создана."):
        add_action(f"Создана категория {category}")

    return result


def _change_answer_reply(category, response) -> str:
    """Меняет первый ответ категории."""

    try:
        result = change_category_answer(category, response)
    except (OSError, ValueError):
        return (
            "Не удалось изменить ответ. "
            "Проверь файл intents.json."
        )

    if result.endswith("изменён."):
        add_action(f"Изменён ответ категории {category}")

    return result


def _remove_phrase_reply(category, phrase) -> str:
    """Удаляет фразу из категории."""

    try:
        result = remove_phrase(category, phrase)
    except (OSError, ValueError):
        return (
            "Не удалось удалить фразу. "
            "Проверь файл intents.json."
        )

    if result.startswith("Фраза удалена"):
        add_action(f"Удалена фраза из категории {category}")

    return result


def _remove_category_reply(category) -> str:
    """Удаляет категорию целиком."""

    try:
        result = remove_category(category)
    except (OSError, ValueError):
        return (
            "Не удалось удалить категорию. "
            "Проверь файл intents.json."
        )

    if result.endswith("удалена."):
        add_action(f"Удалена категория {category}")

    return result


def _category_reply(
    action: str,
    category,
    phrase,
    response,
) -> str | None:
    """Создание, изменение и удаление категорий и фраз."""

    if (
        action == "create_category"
        and category is not None
        and phrase is not None
        and response is not None
    ):
        return _create_category_reply(category, phrase, response)

    if (
        action == "change_category_answer"
        and category is not None
        and response is not None
    ):
        return _change_answer_reply(category, response)

    if (
        action == "remove_category_phrase"
        and category is not None
        and phrase is not None
    ):
        return _remove_phrase_reply(category, phrase)

    if action == "remove_category" and category is not None:
        return _remove_category_reply(category)

    return None


def get_confirmation_response(
    message: str,
) -> str | None:
    """Выполняет или отменяет ожидающее системное действие."""

    pending = get_pending_action()

    if not pending:
        return None

    action = pending["action"]
    archive_id = pending.get("archive_id")
    category = pending.get("category")

    if action == "create_archive":
        return _create_archive_reply(message)

    if message in CANCEL_COMMANDS:
        return _cancel_pending(action, archive_id, category)

    if message not in CONFIRM_COMMANDS:
        return None

    phrase = pending.get("phrase")
    response = pending.get("response")

    clear_pending_action()

    for reply in (
        _clear_reply(action),
        _archive_reply(action, archive_id),
        _category_reply(action, category, phrase, response),
    ):
        if reply is not None:
            return reply

    return "Не удалось выполнить системную операцию."
