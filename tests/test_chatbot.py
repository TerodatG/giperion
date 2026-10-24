# Giperion/tests/test_chatbot.py                                  v004
# Автоматические тесты диалоговой логики Giperion.
# Последнее изменение: самоописание при обращении по имени.

from app.core.chatbot import get_response


def test_empty_message_returns_warning() -> None:
    """Проверяет ответ на пустое сообщение."""

    response, save_to_history = get_response("")

    assert "не получил сообщение" in response.lower()
    assert save_to_history is False


def test_time_request_returns_response() -> None:
    """Проверяет ответ на вопрос о времени."""

    response, save_to_history = get_response(
        "сколько сейчас времени"
    )

    assert response.startswith("Сейчас ")
    assert save_to_history is True


def test_identity_is_not_tied_to_one_user() -> None:
    """Самоописание говорит о ядре, а не о личном собеседнике."""

    response, save_to_history = get_response("кто ты")

    assert "Гиперион" in response
    assert "низшего порядка" in response
    assert "0,1" in response
    assert "1,0" in response
    assert "твой" not in response.lower()
    assert save_to_history is True


def test_identity_with_name_and_punctuation() -> None:
    """Обращение «Гиперион, кто ты?» тоже даёт самоописание."""

    for query in (
        "Кто ты?",
        "Гиперион, кто ты?",
        "ты нейросеть",
    ):
        response, save_to_history = get_response(query)

        assert "Гиперион" in response
        assert "низшего порядка" in response
        assert save_to_history is True


def test_system_command_is_not_saved() -> None:
    """Проверяет, что системная команда не записывается в историю."""

    response, save_to_history = get_response(
        "покажи архивы"
    )

    assert response
    assert save_to_history is False