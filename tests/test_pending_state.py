# Giperion/tests/test_pending_state.py                             v001
# Проверки состояния диалога: действия, уточнения и подтверждения.

import pytest

from terminal.core import chatbot, pending_state
from terminal.memory import confirmations, memory, system_commands, system_handler


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    """Каждый тест начинает с чистого состояния диалога."""

    monkeypatch.setattr(
        confirmations,
        "add_action",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        system_commands,
        "add_action",
        lambda *args, **kwargs: 0,
    )

    pending_state.set_state(pending_state.new_state())

    yield

    pending_state.set_state(pending_state.new_state())


def test_action_is_visible_in_current_state() -> None:
    """Установленное действие видно через публичные функции."""

    system_handler.set_pending_action(
        "delete_archive",
        archive_id="00001",
    )

    assert pending_state.has_pending_action()
    assert system_handler.get_pending_action() == {
        "action": "delete_archive",
        "archive_id": "00001",
    }


def test_states_do_not_share_pending_action() -> None:
    """Два чата хранят независимые ожидающие действия."""

    first = pending_state.new_state()
    second = pending_state.new_state()

    pending_state.set_state(first)
    system_handler.set_pending_action("clear_conversations")

    pending_state.set_state(second)

    assert not pending_state.has_pending_action()

    pending_state.set_state(first)

    assert pending_state.has_pending_action()


def test_states_do_not_share_clarification() -> None:
    """Уточнение тоже не переходит между чатами."""

    first = pending_state.new_state()
    second = pending_state.new_state()

    pending_state.set_state(first)
    chatbot.set_pending_clarification("привет")

    pending_state.set_state(second)

    assert pending_state.get_pending_clarification() is None

    pending_state.set_state(first)

    assert pending_state.get_pending_clarification() == "привет"


def test_confirmation_executes_and_clears_action(
    tmp_path,
    monkeypatch,
) -> None:
    """«Подтверждаю» выполняет действие и сбрасывает ожидание."""

    unknown_file = tmp_path / "unknown_messages.json"

    monkeypatch.setattr(
        memory,
        "UNKNOWN_MESSAGES_FILE",
        unknown_file,
    )

    memory.add_unknown_message("тестовая фраза")
    system_handler.set_pending_action("clear_unknown_messages")

    answer, save = chatbot.get_response("подтверждаю")

    assert "очищен" in answer
    assert save is False
    assert not pending_state.has_pending_action()
    assert memory.get_unknown_messages() == []


def test_cancel_clears_action_without_execution(
    tmp_path,
    monkeypatch,
) -> None:
    """«Отмена» убирает ожидание, не трогая данные."""

    unknown_file = tmp_path / "unknown_messages.json"

    monkeypatch.setattr(
        memory,
        "UNKNOWN_MESSAGES_FILE",
        unknown_file,
    )

    memory.add_unknown_message("тестовая фраза")
    system_handler.set_pending_action("clear_unknown_messages")

    answer, save = chatbot.get_response("отмена")

    assert "Данные не изменены" in answer
    assert save is False
    assert not pending_state.has_pending_action()
    assert len(memory.get_unknown_messages()) == 1
