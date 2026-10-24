# Giperion/tests/test_chatbot_modules.py                             v002
# Проверки связи модулей «Интернет» и «Помощь моделей» с чатботом.
# Последнее изменение: заглушки ставятся в этапы chat_pipeline.

from terminal.core import chatbot, chat_pipeline
from terminal.core.opencode_client import OpenCodeError


def test_internet_disabled_is_honest(monkeypatch) -> None:
    """При выключенном модуле поиск не запускается."""

    monkeypatch.setattr(
        chat_pipeline,
        "is_module_enabled",
        lambda key: False,
    )

    answer, save = chatbot.get_response(
        "найди в интернете курс доллара"
    )

    assert "Интернет» выключен" in answer
    assert save is True


def test_internet_search_uses_results(monkeypatch) -> None:
    """При включённом модуле поиск возвращает выжимку."""

    monkeypatch.setattr(
        chat_pipeline,
        "is_module_enabled",
        lambda key: key == "internet",
    )
    monkeypatch.setattr(
        chat_pipeline,
        "search_web",
        lambda query: [
            {
                "title": "Курс доллара",
                "snippet": "82 рубля.",
                "source": "example.org",
                "url": "https://example.org",
            }
        ],
    )

    answer, save = chatbot.get_response(
        "найди в интернете курс доллара"
    )

    assert "Курс доллара" in answer
    assert "example.org" in answer
    assert save is True


def test_helper_model_is_called_on_uncertainty(
    monkeypatch,
) -> None:
    """Помощь моделей срабатывает, когда локальные правила молчат."""

    monkeypatch.setattr(
        chat_pipeline,
        "is_module_enabled",
        lambda key: key == "models",
    )
    monkeypatch.setattr(
        chat_pipeline,
        "generate_answer",
        lambda message: None,
    )
    monkeypatch.setattr(
        chat_pipeline,
        "match_intent",
        lambda message: None,
    )
    monkeypatch.setattr(
        chat_pipeline,
        "find_close_pattern",
        lambda message: None,
    )
    monkeypatch.setattr(
        chat_pipeline,
        "ask_helper",
        lambda message: ("Внешний ответ", "DeepSeek"),
    )

    answer, save = chatbot.get_response("абракадабра")

    assert "Внешний ответ" in answer
    assert "DeepSeek" in answer
    assert save is False


def test_helper_model_error_is_shown(monkeypatch) -> None:
    """Ошибка внешней модели не роняет чат."""

    monkeypatch.setattr(
        chat_pipeline,
        "is_module_enabled",
        lambda key: key == "models",
    )
    monkeypatch.setattr(
        chat_pipeline,
        "generate_answer",
        lambda message: None,
    )
    monkeypatch.setattr(
        chat_pipeline,
        "match_intent",
        lambda message: None,
    )
    monkeypatch.setattr(
        chat_pipeline,
        "find_close_pattern",
        lambda message: None,
    )

    def broken_helper(message):
        raise OpenCodeError("сервис недоступен")

    monkeypatch.setattr(chat_pipeline, "ask_helper", broken_helper)

    answer, save = chatbot.get_response("абракадабра")

    assert "Помощь моделей" in answer
    assert "сервис недоступен" in answer
    assert save is False
