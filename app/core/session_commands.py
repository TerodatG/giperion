# Giperion/app/core/session_commands.py                           v001
# Общий разбор команд сеанса для консоли и окна.
# Последнее изменение: выход, системные команды и подтверждения вынесены из входов.

from app.language.text_tools import normalize_message
from app.language.vocabulary.phrases import (
    CANCEL_COMMANDS,
    CONFIRM_COMMANDS,
    EXIT_COMMANDS,
)

# Варианты обращения перед системной командой.
SYSTEM_PREFIXES = (
    "гиперион, система:",
    "гиперион, система",
    "гиперион. система:",
    "гиперион. система",
    "гиперион система:",
    "гиперион система",
)


def is_exit_command(user_message: str) -> bool:
    """Проверяет точное совпадение команды выхода."""

    return normalize_message(user_message) in EXIT_COMMANDS


def extract_system_command(user_message: str) -> str | None:
    """Извлекает команду после обращения «Гиперион, система»."""

    message_lower = user_message.lower().strip()

    for prefix in SYSTEM_PREFIXES:
        if message_lower.startswith(prefix):
            command = user_message[len(prefix):].strip()

            return normalize_message(command)

    return None


def is_confirmation_command(user_message: str) -> bool:
    """Проверяет команду принятия или отмены действия."""

    normalized_message = normalize_message(user_message)

    return (
        normalized_message in CONFIRM_COMMANDS
        or normalized_message in CANCEL_COMMANDS
    )
