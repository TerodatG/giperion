# Giperion/app/core/session_commands.py                           v001
# Общий разбор команд сеанса для консоли и окна.
# Последнее изменение: выход, системные команды и подтверждения вынесены из входов.

from shared.text_tools import normalize_message
from terminal.core.phrases import (
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


# Знаки, которые не должны мешать распознать короткую команду.
COMMAND_PUNCTUATION = " \t\r\n?!.,;:—–-"


def _command_key(user_message: str) -> str:
    """Нормализует короткую команду без завершающей пунктуации."""

    return normalize_message(user_message).strip(COMMAND_PUNCTUATION)


def is_exit_command(user_message: str) -> bool:
    """Проверяет точное совпадение команды выхода."""

    return _command_key(user_message) in EXIT_COMMANDS


def extract_system_command(user_message: str) -> str | None:
    """Извлекает команду после обращения «Гиперион, система»."""

    text = user_message.strip()
    message_lower = text.lower()

    for prefix in SYSTEM_PREFIXES:
        if message_lower.startswith(prefix):
            command = text[len(prefix):].strip()

            return _command_key(command)

    return None


def is_confirmation_command(user_message: str) -> bool:
    """Проверяет команду принятия или отмены действия."""

    normalized_message = _command_key(user_message)

    return (
        normalized_message in CONFIRM_COMMANDS
        or normalized_message in CANCEL_COMMANDS
    )
