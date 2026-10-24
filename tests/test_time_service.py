# Giperion/tests/test_time_service.py                             v002
# Автоматические тесты сервиса времени и даты Giperion.
# Последнее изменение: обновлены импорты после переноса time_service в пакет skills.

from terminal.skills.time_service import (
    get_current_date,
    get_current_time,
    get_current_weekday,
)
from terminal.skills.time_handler import get_time_and_date_response


def test_current_time_has_hours_and_minutes() -> None:
    """Проверяет формат текущего времени."""

    current_time = get_current_time()

    assert len(current_time) == 5
    assert current_time[2] == ":"


def test_current_date_is_not_empty() -> None:
    """Проверяет получение текущей даты."""

    assert get_current_date()


def test_current_weekday_is_not_empty() -> None:
    """Проверяет получение текущего дня недели."""

    assert get_current_weekday()


def test_time_question_in_colloquial_form() -> None:
    """«Какое время щас» должно вести к настоящим часам, а не к заглушке."""

    answer = get_time_and_date_response("какое время щас")

    assert answer is not None
    assert answer.startswith("Сейчас ")