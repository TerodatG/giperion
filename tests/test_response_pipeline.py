# Giperion/tests/test_response_pipeline.py                         v002
# Проверки порядка этапов ответа и состояния уточнения.
# Последнее изменение: заглушки ставятся в chat_pipeline, порядок зафиксирован.

import pytest

from kraper_model import api
from kraper_model.identity_matrix import IDENTITY_MATRIX
from kraper_model.language.intent_handler import find_intent_response
from terminal.core import chat_pipeline, chatbot
from terminal.core.chat_pipeline import STAGES
from terminal.memory import memory, system_handler


@pytest.fixture()
def isolated_chatbot(tmp_path, monkeypatch):
    """Изолирует память и отключает сеть, модели и помощника."""

    monkeypatch.setattr(
        memory,
        "CONVERSATIONS_FILE",
        tmp_path / "conversations.json",
    )
    monkeypatch.setattr(
        memory,
        "UNKNOWN_MESSAGES_FILE",
        tmp_path / "unknown_messages.json",
    )
    monkeypatch.setattr(
        memory,
        "USER_PROFILE_FILE",
        tmp_path / "user_profile.json",
    )
    monkeypatch.setattr(
        chat_pipeline,
        "generate_answer",
        lambda text: None,
    )
    monkeypatch.setattr(chat_pipeline, "ask_helper", lambda text: None)
    monkeypatch.setattr(
        chat_pipeline,
        "is_module_enabled",
        lambda key: False,
    )

    chatbot.clear_pending_clarification()
    system_handler.clear_pending_action()

    yield

    chatbot.clear_pending_clarification()
    system_handler.clear_pending_action()


def test_stage_order_is_fixed() -> None:
    """Порядок этапов зафиксирован и не меняется случайно."""

    assert [name for name, _ in STAGES] == [
        "identity",
        "confirmation",
        "system_command",
        "characteristics",
        "clean_learned",
        "clear_variables",
        "show_variables",
        "show_unknown",
        "learning",
        "system_mode_guard",
        "web_search",
        "help",
        "time",
        "math",
        "name",
        "profile",
        "intent",
        "neural",
        "helper_model",
        "close_pattern",
        "unknown",
    ]


def test_pipeline_stops_at_first_handled_stage(
    isolated_chatbot,
    monkeypatch,
) -> None:
    """Первый этап, вернувший ответ, останавливает цепочку."""

    calls = []

    def first_stage(context):
        calls.append("first")

        return ("первый ответ", True)

    def second_stage(context):
        calls.append("second")

        return ("второй ответ", True)

    monkeypatch.setattr(
        chatbot,
        "STAGES",
        (
            ("first", first_stage),
            ("second", second_stage),
        ),
    )

    answer, save = chatbot.get_response("тест")

    assert answer == "первый ответ"
    assert save is True
    assert calls == ["first"]


def test_identity_wins_over_neural(
    isolated_chatbot,
    monkeypatch,
) -> None:
    """Вопрос о себе не уходит ни в сеть, ни в нейросеть."""

    calls = []

    def fake_neural(text):
        calls.append(text)

        return api.ModelReply("нейросетевой ответ", "neural", 0.9)

    monkeypatch.setattr(
        chat_pipeline,
        "generate_answer",
        fake_neural,
    )

    answer, save = chatbot.get_response("Гиперион, кто ты?")

    assert answer == IDENTITY_MATRIX["self_description"]
    assert save is True
    assert calls == []


def test_exact_intent_wins_over_neural(
    isolated_chatbot,
    monkeypatch,
) -> None:
    """Точное знание важнее генерации."""

    expected = find_intent_response("привет")
    calls = []

    def fake_neural(text):
        calls.append(text)

        return api.ModelReply("нейросетевой ответ", "neural", 0.9)

    monkeypatch.setattr(
        chat_pipeline,
        "generate_answer",
        fake_neural,
    )

    answer, save = chatbot.get_response("привет")

    assert expected
    assert answer == expected
    assert save is True
    assert calls == []


def test_system_mode_does_not_call_neural(
    isolated_chatbot,
    monkeypatch,
) -> None:
    """Неизвестная системная команда не уходит в нейросеть."""

    def fake_neural(text):
        raise AssertionError("нейросеть не должна вызываться")

    monkeypatch.setattr(
        chat_pipeline,
        "generate_answer",
        fake_neural,
    )

    answer, save = chatbot.get_response(
        "абракадабраззз",
        is_system_mode=True,
    )

    assert answer == "Нет такой системной команды."
    assert save is False


def test_unknown_phrase_is_saved(
    isolated_chatbot,
    monkeypatch,
) -> None:
    """Неизвестная фраза сохраняется и получает честный отказ."""

    monkeypatch.setattr(
        chat_pipeline,
        "find_close_pattern",
        lambda text: None,
    )

    answer, save = chatbot.get_response("абракадабраззз")

    assert "не знаю" in answer
    assert save is True

    unknown = memory.get_unknown_messages()

    assert len(unknown) == 1
    assert unknown[0]["text"] == "абракадабраззз"


def test_yes_confirms_pending_clarification(
    isolated_chatbot,
) -> None:
    """Ответ «да» повторяет фразу, которую предложили уточнить."""

    chatbot.set_pending_clarification("привет")

    answer, save = chatbot.get_response("да")

    assert answer == find_intent_response("привет")
    assert save is True
    assert chatbot.get_clarification_response("да", False) is None


def test_no_declines_pending_clarification(
    isolated_chatbot,
) -> None:
    """Ответ «нет» сбрасывает уточнение и просит переформулировать."""

    chatbot.set_pending_clarification("привет")

    answer, save = chatbot.get_response("нет")

    assert "Повтори вопрос другими словами" in answer
    assert save is True
    assert chatbot.get_clarification_response("да", False) is None
