# Giperion/app/memory/system_commands.py                          v001
# Разбор системных команд памяти и архивов, ответы-списки.
# Последнее изменение: выделено из system_handler.

import re

from shared.action_log import (
    add_action,
    get_recent_actions,
)
from app.core.pending_state import set_pending_action
from app.help_handler import get_help_response
from app.language.vocabulary.phrases import (
    CLEAR_CONVERSATIONS_COMMANDS,
    CLEAR_UNKNOWN_MESSAGES_COMMANDS,
    CREATE_ARCHIVE_COMMANDS,
    RESET_CORE_COMMANDS,
    SHOW_ARCHIVES_COMMANDS,
)
from app.memory.archive_service import (
    create_archive,
    format_archive_datetime,
    get_archive_files,
    get_archive_info,
    get_archives,
)

RESTORE_ARCHIVE_PATTERN = re.compile(
    r"^восстановить\s+архив\s+(\d{5})$"
)
DELETE_ARCHIVE_PATTERN = re.compile(
    r"^удалить\s+архив\s+(\d{5})$"
)
SHOW_ARCHIVE_FILES_PATTERN = re.compile(
    r"^покажи\s+файлы\s+архива(?:\s+(\d{5}))?$"
)

SHOW_ACTION_LOG_COMMANDS = {
    "покажи журнал действий",
    "журнал действий",
    "последние действия",
}

SYSTEM_HELP_COMMANDS = {
    "помощ",
    "помощь",
}


def get_confirmation_message(description: str) -> str:
    """Формирует запрос подтверждения системного действия."""

    return (
        f"{description} "
        "Для выполнения напиши: подтверждаю. "
        "Для отмены напиши: отмена."
    )


def get_archives_response() -> str:
    """Формирует список архивов."""

    archives = get_archives()

    if not archives:
        return "Архивов памяти пока нет."

    lines = ["Доступные архивы:"]

    for number, archive in enumerate(archives, start=1):
        archive_id = archive["archive_id"]
        created_at = format_archive_datetime(
            archive["created_at"]
        )
        lines.append(
            f"{number}. {archive_id} — {created_at}"
        )

    return "\n".join(lines)


def get_archive_files_response(
    archive_id: str | None,
) -> str:
    """Возвращает файлы выбранного или последнего архива."""

    archives = get_archives()

    if not archives:
        return "Архивов памяти пока нет."

    if archive_id is None:
        archive_id = archives[0]["archive_id"]

    archive_info = get_archive_info(archive_id)

    if not archive_info:
        return f"Архив {archive_id} не найден."

    archive_files = get_archive_files(archive_id)

    if archive_files is None:
        return (
            "Не удалось прочитать файлы архива "
            f"{archive_id}."
        )

    created_at = format_archive_datetime(
        archive_info["created_at"]
    )

    lines = [
        f"Файлы архива {archive_id} — {created_at}:"
    ]

    for file_name in archive_files:
        lines.append(f"- {file_name}")

    return "\n".join(lines)


def get_action_log_response() -> str:
    """Показывает десять последних действий."""

    actions = get_recent_actions()

    if not actions:
        return "Журнал действий пока пуст."

    return "\n".join(
        ["Последние действия:", *actions]
    )


def create_archive_response() -> str:
    """Создаёт архив и записывает выполненное действие."""

    archive_info = create_archive()
    archive_id = archive_info["archive_id"]

    add_action(f"Создан архив {archive_id}")

    created_at = format_archive_datetime(
        archive_info["created_at"]
    )

    return (
        f"Архив создан. {created_at} — {archive_id}."
    )


def get_system_command_response(
    message: str,
) -> str | None:
    """Обрабатывает системные команды памяти и архивов."""

    if message in SYSTEM_HELP_COMMANDS:
        return get_help_response("помощь")

    if message in SHOW_ACTION_LOG_COMMANDS:
        return get_action_log_response()

    show_files_match = SHOW_ARCHIVE_FILES_PATTERN.fullmatch(
        message
    )

    if show_files_match:
        return get_archive_files_response(
            show_files_match.group(1)
        )

    if message in SHOW_ARCHIVES_COMMANDS:
        return get_archives_response()

    if message in CREATE_ARCHIVE_COMMANDS:
        set_pending_action("create_archive")

        return "Создать архив? Да/Нет"

    if message in CLEAR_UNKNOWN_MESSAGES_COMMANDS:
        set_pending_action("clear_unknown_messages")

        return get_confirmation_message(
            "Будет очищен список непонятых фраз."
        )

    if message in CLEAR_CONVERSATIONS_COMMANDS:
        set_pending_action("clear_conversations")

        return get_confirmation_message(
            "Будет очищена вся история переписки."
        )

    if message in RESET_CORE_COMMANDS:
        set_pending_action("reset_core")

        return get_confirmation_message(
            "Будут очищены имя пользователя, история переписки "
            "и список непонятых фраз. Код, навыки и файлы проекта "
            "останутся без изменений."
        )

    restore_match = RESTORE_ARCHIVE_PATTERN.fullmatch(
        message
    )

    if restore_match:
        archive_id = restore_match.group(1)

        if not get_archive_info(archive_id):
            return f"Архив {archive_id} не найден."

        set_pending_action(
            "restore_archive",
            archive_id=archive_id,
        )

        return get_confirmation_message(
            "Будут восстановлены имя пользователя, "
            "история переписки и список непонятых фраз "
            f"из архива {archive_id}."
        )

    delete_match = DELETE_ARCHIVE_PATTERN.fullmatch(
        message
    )

    if delete_match:
        archive_id = delete_match.group(1)

        if not get_archive_info(archive_id):
            return f"Архив {archive_id} не найден."

        set_pending_action(
            "delete_archive",
            archive_id=archive_id,
        )

        return get_confirmation_message(
            f"Архив {archive_id} будет удалён "
            "без возможности восстановления."
        )

    return None
