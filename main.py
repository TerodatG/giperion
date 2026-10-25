# Giperion/main.py                                              v017
# Запуск консольного ИИ-собеседника Гиперион.
# Последнее изменение: общие команды сеанса и состояние диалога из app/core.

from colorama import (
    Fore,
    Style,
    just_fix_windows_console,
)

from shared.action_log import add_action
from shared.text_tools import (
    normalize_message,
)
from terminal.core.character_handler import (
    get_characteristics_response,
)
from terminal.core.chatbot import get_response
from terminal.core.pending_state import has_pending_action
from terminal.core.session_commands import (
    extract_system_command,
    is_confirmation_command,
    is_exit_command,
)
from terminal.memory.memory import add_message

BOT_NAME = "Гиперион"

USER_LABEL_COLOR = Fore.WHITE
BOT_LABEL_COLOR = Fore.GREEN
BOT_TEXT_COLOR = Fore.GREEN
PARAMETERS_COLOR = Fore.CYAN
VARIABLES_COLOR = Fore.LIGHTYELLOW_EX
SYSTEM_COLOR = Fore.YELLOW
RESET_COLOR = Style.RESET_ALL


def print_bot_message(
    message: str,
) -> None:
    """Выводит обычный ответ Гипериона зелёным цветом."""

    print(
        f"{BOT_LABEL_COLOR}"
        f"{BOT_NAME}:{RESET_COLOR} "
        f"{BOT_TEXT_COLOR}"
        f"{message}{RESET_COLOR}"
    )


def print_parameters_message(
    message: str,
) -> None:
    """Выводит параметры ядра голубым цветом."""

    print(
        f"{BOT_LABEL_COLOR}"
        f"{BOT_NAME}:{RESET_COLOR} "
        f"{PARAMETERS_COLOR}"
        f"{message}{RESET_COLOR}"
    )


def print_variables_message(
    message: str,
) -> None:
    """Выводит переменные жёлтым цветом."""

    print(
        f"{BOT_LABEL_COLOR}"
        f"{BOT_NAME}:{RESET_COLOR} "
        f"{VARIABLES_COLOR}"
        f"{message}{RESET_COLOR}"
    )


def print_system_message(
    message: str,
) -> None:
    """Выводит системное сообщение Гипериона жёлтым цветом."""

    print(
        f"{SYSTEM_COLOR}"
        f"[СИСТЕМА]: "
        f"{message}{RESET_COLOR}"
    )


def get_user_message() -> str:
    """Получает ввод пользователя с белым приглашением."""

    return input(
        f"\n{USER_LABEL_COLOR}"
        f"Ты:{RESET_COLOR} "
    ).strip()


def is_parameters_response(
    message: str,
) -> bool:
    """Определяет ответ со статистикой ядра."""

    return (
        message.startswith(
            "Параметры ИИ-ядра:"
        )
        or message.startswith(
            "Статистика ИИ-ядра:"
        )
        or message.startswith(
            "Характеристики ИИ-ядра:"
        )
    )


def is_variables_response(
    message: str,
) -> bool:
    """Определяет ответ с переменными калькулятора."""

    return (
        message.startswith(
            "Переменные:"
        )
        or message.startswith(
            "Сохранённые переменные:"
        )
        or message.startswith(
            "Временные переменные очищены."
        )
        or message.startswith(
            "Переменных пока нет."
        )
    )


def print_response(
    message: str,
) -> None:
    """Выбирает цвет для обычного ответа."""

    if is_parameters_response(message):
        print_parameters_message(message)
        return

    if is_variables_response(message):
        print_variables_message(message)
        return

    print_bot_message(message)


def process_system_command(
    command: str,
) -> None:
    """Выполняет системную команду без сохранения истории."""

    if not command:
        print_system_message(
            "После слова «система» напиши команду. "
            "Например: «Гиперион, система: "
            "покажи архивы»."
        )
        return

    response, _ = get_response(
        command,
        is_system_mode=True,
    )

    print_system_message(response)


def main() -> None:
    """Запускает консольный диалог Гипериона."""

    just_fix_windows_console()

    add_action("Гиперион запущен")

    print_system_message(
        "Гиперион запущен. "
        "Для системных команд используй формат: "
        "«Гиперион, система: команда»."
    )
    print_system_message(
        "Для завершения работы напиши: выход."
    )
    print()

    print_parameters_message(
        get_characteristics_response()
    )

    while True:
        user_message = (
            get_user_message()
        )

        if not user_message:
            print_bot_message(
                "Я не получил сообщение."
            )
            continue

        if is_exit_command(
            user_message
        ):
            add_action(
                "Гиперион завершил работу"
            )
            print_bot_message(
                "Увидимся!"
            )
            break

        system_command = extract_system_command(
            user_message
        )

        if system_command is not None:
            process_system_command(
                system_command
            )
            continue

        if (
            has_pending_action()
            and is_confirmation_command(
                user_message
            )
        ):
            process_system_command(
                normalize_message(user_message)
            )
            continue

        response, save_to_history = (
            get_response(user_message)
        )

        print_response(
            response
        )

        if save_to_history:
            add_message(
                "user",
                user_message,
            )
            add_message(
                "assistant",
                response,
            )


if __name__ == "__main__":
    main()
