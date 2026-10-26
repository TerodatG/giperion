# Giperion/terminal/core/chatbot.py                                v039
# Координация ответов Гипериона на сообщения пользователя.
# Последнее изменение: необязательная личность дрона.

from shared.text_tools import normalize_message
from terminal.core.chat_pipeline import STAGES, ChatContext
from terminal.core.pending_state import (
    clear_pending_clarification,
    get_pending_clarification,
    set_pending_clarification,  # noqa: F401 — точка подмены в тестах
)
from terminal.core.phrases import NO_ANSWERS, YES_ANSWERS


def get_clarification_response(
    message: str,
    is_system_mode: bool,
    persona: dict | None = None,
) -> tuple[str, bool] | None:
    """Обрабатывает ответ пользователя на предложенное уточнение."""

    pending = get_pending_clarification()

    if is_system_mode or pending is None:
        return None

    if message in YES_ANSWERS:
        clarified_phrase = pending
        clear_pending_clarification()

        return get_response(
            clarified_phrase,
            persona=persona,
        )

    if message in NO_ANSWERS:
        clear_pending_clarification()

        return (
            "Хорошо. Повтори вопрос другими словами.",
            True,
        )

    clear_pending_clarification()

    return None


def get_response(
    user_message: str,
    is_system_mode: bool = False,
    persona: dict | None = None,
) -> tuple[str, bool]:
    """Возвращает ответ и признак сохранения диалога в историю.

    Уточнение проверяется отдельно: оно может рекурсивно повторить
    исходную фразу. Остальные шаги идут по фиксированному порядку
    STAGES, и первый обработавший запрос останавливает цепочку.
    """

    message = normalize_message(user_message)

    if not message:
        return (
            "Я не получил сообщение. "
            "Напиши, пожалуйста, "
            "что-нибудь.",
            False,
        )

    clarification_response = get_clarification_response(
        message,
        is_system_mode,
        persona,
    )

    if clarification_response:
        return clarification_response

    context = ChatContext(
        message=message,
        user_message=user_message,
        is_system_mode=is_system_mode,
        persona=persona,
    )

    for _, stage in STAGES:
        result = stage(context)

        if result is not None:
            return result

    # Страховка: последний этап unknown_stage всегда отвечает.
    return (
        "Я пока не знаю, как на это ответить.",
        True,
    )
