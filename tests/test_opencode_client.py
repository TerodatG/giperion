# Giperion/tests/test_opencode_client.py                          v001
# Проверки разбора ответа локального сервиса OpenCode.
# Последнее изменение: извлечение текста и расхода токенов без сети.

import pytest

from terminal.core.opencode_client import OpenCodeError, extract_answer


def build_messages(*assistants: dict) -> dict:
    """Собирает переписку с пользовательской репликой и ответами."""

    return {
        "data": [
            {"type": "user", "text": "привет"},
            *assistants,
        ]
    }


def test_extract_answer_takes_latest_assistant() -> None:
    """Берётся самый свежий ответ, служебные части пропускаются."""

    old = {
        "type": "assistant",
        "time": {"created": 1},
        "content": [{"type": "text", "text": "старый"}],
        "tokens": {"input": 10, "output": 1},
    }
    new = {
        "type": "assistant",
        "time": {"created": 2},
        "content": [
            {"type": "reasoning", "text": "думаю"},
            {"type": "text", "text": "свежий"},
            {"type": "text", "text": "ответ"},
        ],
        "tokens": {"input": 20, "output": 5, "reasoning": 2},
    }

    answer, usage = extract_answer(build_messages(old, new))

    assert answer == "свежий\n\nответ"
    assert usage == {
        "input": 20,
        "output": 5,
        "reasoning": 2,
        "total": 27,
    }


def test_extract_answer_requires_text() -> None:
    """Ответ без текстовых частей считается пустым."""

    message = {
        "type": "assistant",
        "time": {"created": 1},
        "content": [{"type": "reasoning", "text": "думаю"}],
        "tokens": {},
    }

    with pytest.raises(OpenCodeError):
        extract_answer(build_messages(message))


def test_extract_answer_reports_model_error() -> None:
    """Ошибка модели превращается в понятное исключение."""

    message = {
        "type": "assistant",
        "time": {"created": 1},
        "content": [],
        "error": {"message": "нет ключа"},
    }

    with pytest.raises(OpenCodeError, match="нет ключа"):
        extract_answer(build_messages(message))
