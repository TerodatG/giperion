# Giperion/tests/test_conference.py                                 v003
# Проверки параллельного совета моделей.
# Последнее изменение: три сенатора по репутации.

from terminal.core import conference, conference_roster
from terminal.core.opencode_client import OpenCodeError


def test_council_collects_all_replies(monkeypatch) -> None:
    """Все участники отвечают, порядок сохраняется."""

    prompts = []

    def fake_ask(model_id, text, provider_id, title):
        prompts.append(text)

        return ("внешний ответ", {"total": 7})

    monkeypatch.setattr(conference, "ask_model", fake_ask)
    monkeypatch.setattr(
        conference,
        "get_response",
        lambda text: ("локальный ответ", True),
    )
    monkeypatch.setattr(
        conference,
        "record_model_request",
        lambda *args, **kwargs: None,
    )

    participants = [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "available": True,
            "model_id": "deepseek-test",
            "provider_id": "opencode",
        },
        {
            "id": "giperion",
            "name": "Гиперион",
        },
    ]

    replies = conference.ask_conference(
        participants,
        "Что дальше?",
        "Пользователь: Привет",
    )

    assert [reply.name for reply in replies] == [
        "Гиперион",
        "DeepSeek",
    ]
    assert replies[0].text == "локальный ответ"
    assert replies[1].text == "внешний ответ"
    assert "Пользователь: Привет" in prompts[0]


def test_reputation_orders_replies(monkeypatch) -> None:
    """После Гипериона ответы идут по убыванию репутации."""

    def fake_ask(model_id, text, provider_id, title):
        return (f"ответ {model_id}", {"total": 1})

    monkeypatch.setattr(conference, "ask_model", fake_ask)
    monkeypatch.setattr(
        conference,
        "get_response",
        lambda text: ("локальный ответ", True),
    )
    monkeypatch.setattr(
        conference,
        "record_model_request",
        lambda *args, **kwargs: None,
    )
    reputations = {
        "deepseek": {"requests": 2},
        "glm": {"requests": 7},
        "giperion": {"requests": 1},
    }
    monkeypatch.setattr(
        conference_roster,
        "get_reputation",
        lambda model_id: reputations.get(
            model_id,
            {"requests": 0},
        ),
    )

    participants = [
        {
            "id": "deepseek",
            "name": "DeepSeek",
            "available": True,
            "model_id": "deepseek-test",
            "provider_id": "opencode",
        },
        {
            "id": "glm",
            "name": "GLM",
            "available": True,
            "model_id": "glm-test",
            "provider_id": "opencode",
        },
        {"id": "giperion", "name": "Гиперион"},
    ]

    replies = conference.ask_conference(participants, "Привет")

    assert [reply.model_id for reply in replies] == [
        "giperion",
        "glm",
        "deepseek",
    ]


def test_conference_keeps_three_best(monkeypatch) -> None:
    """В совет проходят только три модели с лучшей репутацией."""

    monkeypatch.setattr(
        conference,
        "ask_model",
        lambda model_id, text, provider_id, title: (
            f"ответ {model_id}",
            {"total": 1},
        ),
    )
    monkeypatch.setattr(
        conference,
        "get_response",
        lambda text: ("локальный ответ", True),
    )
    monkeypatch.setattr(
        conference,
        "record_model_request",
        lambda *args, **kwargs: None,
    )
    reputations = {
        "m1": {"requests": 1},
        "m2": {"requests": 9},
        "m3": {"requests": 5},
        "m4": {"requests": 7},
    }
    monkeypatch.setattr(
        conference_roster,
        "get_reputation",
        lambda model_id: reputations.get(
            model_id,
            {"requests": 0},
        ),
    )

    participants = [
        {
            "id": model_id,
            "name": model_id.upper(),
            "available": True,
            "model_id": f"{model_id}-test",
            "provider_id": "opencode",
        }
        for model_id in ("m1", "m2", "m3", "m4")
    ]

    replies = conference.ask_conference(participants, "Привет")

    assert [reply.model_id for reply in replies] == [
        "m2",
        "m4",
        "m3",
    ]
    assert [reply.senator for reply in replies] == [1, 2, 3]


def test_unavailable_model_returns_error(monkeypatch) -> None:
    """Ошибка одной модели не мешает остальным."""

    def broken_ask(model_id, text, provider_id, title):
        raise OpenCodeError("нет связи")

    monkeypatch.setattr(conference, "ask_model", broken_ask)
    monkeypatch.setattr(
        conference,
        "record_model_request",
        lambda *args, **kwargs: None,
    )

    replies = conference.ask_conference(
        [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "available": True,
                "model_id": "deepseek-test",
                "provider_id": "opencode",
            }
        ],
        "Привет",
    )

    assert len(replies) == 1
    assert replies[0].error is True
    assert "не ответила" in replies[0].text
