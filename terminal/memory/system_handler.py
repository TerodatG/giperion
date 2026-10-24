# Giperion/app/memory/system_handler.py                         v012
# Совместимый фасад системных команд и подтверждений Гипериона.
# Последнее изменение: реализация разделена на system_commands и confirmations.

from terminal.core.pending_state import (
    clear_pending_action,
    get_pending_action,
    set_pending_action,
)
from terminal.memory.confirmations import get_confirmation_response
from terminal.memory.system_commands import (
    create_archive_response,
    get_action_log_response,
    get_archive_files_response,
    get_archives_response,
    get_confirmation_message,
    get_system_command_response,
)

__all__ = [
    "clear_pending_action",
    "create_archive_response",
    "get_action_log_response",
    "get_archive_files_response",
    "get_archives_response",
    "get_confirmation_message",
    "get_confirmation_response",
    "get_pending_action",
    "get_system_command_response",
    "set_pending_action",
]
