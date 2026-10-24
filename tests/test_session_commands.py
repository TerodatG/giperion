# Giperion/tests/test_session_commands.py                          v001
# Проверки общего разбора команд для консоли и окна.

from app.core.session_commands import (
    extract_system_command,
    is_confirmation_command,
    is_exit_command,
)


def test_exit_commands_are_recognized() -> None:
    """Выход понимается в нормализованном виде."""

    assert is_exit_command("Выход")
    assert is_exit_command("  выход ")


def test_regular_message_is_not_exit() -> None:
    """Обычная фраза не считается командой выхода."""

    assert not is_exit_command("привет")


def test_system_command_is_extracted() -> None:
    """Команда извлекается после любого варианта обращения."""

    assert (
        extract_system_command("Гиперион, система: покажи архивы")
        == "покажи архивы"
    )
    assert (
        extract_system_command("Гиперион система: покажи архивы")
        == "покажи архивы"
    )
    assert (
        extract_system_command("Гиперион. Система: покажи архивы")
        == "покажи архивы"
    )


def test_empty_system_command_returns_empty_string() -> None:
    """Пустая команда после обращения остаётся пустой."""

    assert extract_system_command("Гиперион, система:") == ""


def test_regular_message_is_not_system_command() -> None:
    """Без обращения команда не извлекается."""

    assert extract_system_command("покажи архивы") is None


def test_confirmation_and_cancel_are_recognized() -> None:
    """Подтверждение и отмена распознаются одинаково в обоих входах."""

    for phrase in ("подтверждаю", "принять", "отмена", "отменить"):
        assert is_confirmation_command(phrase)

    # «Да/нет» обрабатывает get_confirmation_response: у них есть
    # приоритет как у ответа на уточнение, поэтому вход их не перехватывает.
    assert not is_confirmation_command("да")
    assert not is_confirmation_command("нет")


def test_regular_message_is_not_confirmation() -> None:
    """Обычная фраза не считается подтверждением."""

    assert not is_confirmation_command("расскажи анекдот")
