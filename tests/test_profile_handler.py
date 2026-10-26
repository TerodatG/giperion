# Giperion/tests/test_profile_handler.py                            v001
# Проверки имени пользователя: явные формы и вопросы профиля.

import pytest

from shared.text_tools import normalize_message
from terminal.memory import memory
from terminal.memory.profile_handler import (
    get_name_from_message,
    get_name_response,
)


@pytest.fixture()
def profile_file(tmp_path, monkeypatch):
    """Направляет профиль пользователя во временный файл."""

    path = tmp_path / "user_profile.json"

    monkeypatch.setattr(memory, "USER_PROFILE_FILE", path)

    return path


def test_state_is_not_taken_as_name(profile_file) -> None:
    """«Я устал» — это состояние, а не имя."""

    assert get_name_from_message("я устал") is None
    assert get_name_response(normalize_message("я устал")) is None
    assert get_name_response(normalize_message("я голоден")) is None


def test_explicit_name_forms_are_accepted(profile_file) -> None:
    """Имя задаётся только явной формой."""

    assert get_name_from_message("меня зовут Влад") == "Влад"
    assert get_name_from_message("моё имя Влад") == "Влад"
    assert get_name_from_message("мое имя Влад") == "Влад"
    assert get_name_from_message("я — Влад") == "Влад"
    assert get_name_from_message("я, Влад") == "Влад"


def test_profile_questions_work_with_yo(profile_file) -> None:
    """Вопросы с «ё» и «е» одинаково возвращают сохранённое имя."""

    memory.set_user_name("Влад")

    for question in (
        "ты помнишь моё имя",
        "ты помнишь мое имя",
        "назови моё имя",
        "назови мое имя",
        "как меня зовут",
        "какое у меня имя",
    ):
        answer = get_name_response(normalize_message(question))

        assert answer is not None
        assert "Влад" in answer
