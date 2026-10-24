# Giperion/tests/test_model_errors.py                              v001
# Проверки понятных ошибок внешних моделей и локального запасного ответа.
# Последнее изменение: лимит OpenCode распознаётся и переводится.

from app.core.model_engine import describe_model_error


def test_quota_error_is_translated() -> None:
    """Английский текст лимита превращается в короткую русскую фразу."""

    text = describe_model_error(
        "DeepSeek",
        "Модель сообщила об ошибке: Free usage limit reached. "
        "Connect a provider or subscribe to OpenCode Go.",
    )

    assert "DeepSeek" in text
    assert "лимит" in text.lower()
    assert "OpenCode Go" in text
    assert "Free usage limit" not in text


def test_unknown_error_keeps_short_detail() -> None:
    """Неизвестная ошибка остаётся в системном сообщении коротко."""

    text = describe_model_error("GLM", "Сервис OpenCode недоступен.")

    assert "GLM" in text
    assert "OpenCode недоступен" in text
    assert len(text) < 240


def test_quota_error_stops_history(monkeypatch) -> None:
    """Ошибка лимита не считается ответом модели."""

    from app.core import model_engine
    from app.core.opencode_client import OpenCodeError

    def broken_ask(model_id, text, provider_id, title):
        raise OpenCodeError(
            "Модель сообщила об ошибке: Free usage limit reached."
        )

    monkeypatch.setattr(
        model_engine,
        "get_current_model_id",
        lambda: "deepseek",
    )
    monkeypatch.setattr(
        model_engine,
        "get_model",
        lambda model_id: {
            "name": "DeepSeek",
            "available": True,
            "model_id": "deepseek-test",
            "provider_id": "opencode",
        },
    )
    monkeypatch.setattr(
        model_engine,
        "record_model_request",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(model_engine, "ask_model", broken_ask)

    response = model_engine.get_model_response("привет")

    assert response.error is True
    assert response.save_to_history is False
    assert "лимит" in response.text.lower()

    # Старая распаковка в пару продолжает работать.
    text, save = response

    assert text == response.text
    assert save is False


def test_helper_limit_is_marked_on_core_response(
    monkeypatch,
) -> None:
    """Ошибка модели-помощника помечает ответ ядра, а не тонет в тексте."""

    from app.core import chat_pipeline
    from app.core.opencode_client import OpenCodeError

    monkeypatch.setattr(
        chat_pipeline,
        "is_module_enabled",
        lambda key: True,
    )

    def broken_helper(message):
        raise OpenCodeError(
            "Модель сообщила об ошибке: Free usage limit reached."
        )

    monkeypatch.setattr(
        chat_pipeline,
        "ask_helper",
        broken_helper,
    )

    result = chat_pipeline.helper_model_stage(
        chat_pipeline.ChatContext(
            message="привет",
            user_message="привет",
            is_system_mode=False,
        )
    )

    assert result is not None
    assert result.external_error
    assert "лимит" in result.external_error.lower()

    text, save = result

    assert text == result.external_error
    assert save is False


def test_local_model_flags_helper_error(monkeypatch) -> None:
    """Ответ локального ядра с ошибкой помощника идёт в системный лог."""

    from app.core import chat_pipeline, model_engine

    monkeypatch.setattr(
        model_engine,
        "get_current_model_id",
        lambda: "giperion",
    )
    monkeypatch.setattr(
        model_engine,
        "record_model_request",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        model_engine,
        "get_response",
        lambda text: chat_pipeline.CoreResponse(
            "Модель «Помощь моделей»: бесплатный лимит исчерпан.",
            False,
            "Модель «Помощь моделей»: бесплатный лимит исчерпан.",
        ),
    )

    response = model_engine.get_model_response("привет")

    assert response.error is True
    assert response.save_to_history is False
    assert "лимит" in response.text.lower()
