# Giperion/tests/test_knowledge_management.py                    v001
# Проверки просмотра и изменения обучающих данных Giperion.
# Последнее изменение: добавлены тесты подтверждения, отмены и сохранения _meta.

import json

import pytest

from shared import action_log
from app.core.chatbot import get_response
from giperion.language import (
    intent_handler,
    learning_service,
)
from app.memory import system_handler


@pytest.fixture
def isolated_knowledge(tmp_path, monkeypatch):
    """Создаёт временные обучающие данные и журнал."""

    intents_file = tmp_path / "intents.json"
    log_file = tmp_path / "logs" / "actions.log"

    document = {
        "_meta": {
            "version": "v002",
        },
        "intents": [
            {
                "tag": "project",
                "patterns": [
                    "как идет проект",
                    "что нового в проекте",
                ],
                "responses": [
                    "Мы развиваем Giperion",
                    "Работа продолжается",
                ],
            },
        ],
    }

    intents_file.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        learning_service,
        "INTENTS_FILE",
        intents_file,
    )
    monkeypatch.setattr(
        intent_handler,
        "INTENTS_FILE",
        intents_file,
    )
    monkeypatch.setattr(
        action_log,
        "LOG_FILE",
        log_file,
    )

    system_handler.clear_pending_action()

    yield {
        "intents_file": intents_file,
        "log_file": log_file,
    }

    system_handler.clear_pending_action()


def read_document(isolated_knowledge) -> dict:
    """Читает временный JSON теста."""

    return json.loads(
        isolated_knowledge[
            "intents_file"
        ].read_text(
            encoding="utf-8"
        )
    )


def test_show_category_does_not_change_data(
    isolated_knowledge,
) -> None:
    """Просмотр показывает фразы и ответы без записи."""

    before = isolated_knowledge[
        "intents_file"
    ].read_text(encoding="utf-8")

    response, save_to_history = get_response(
        "покажи фразы категории project"
    )

    assert "как идет проект" in response
    assert "Мы развиваем Giperion" in response
    assert save_to_history is False
    assert isolated_knowledge[
        "intents_file"
    ].read_text(encoding="utf-8") == before


def test_change_answer_requires_confirmation(
    isolated_knowledge,
) -> None:
    """Ответ меняется только после подтверждения."""

    request, save_request = get_response(
        "измени ответ категории project: "
        "Проект развивается"
    )

    assert "подтверждаю" in request
    assert save_request is False
    assert read_document(
        isolated_knowledge
    )["intents"][0]["responses"][0] == (
        "Мы развиваем Giperion"
    )

    result, save_result = get_response(
        "подтверждаю"
    )

    responses = read_document(
        isolated_knowledge
    )["intents"][0]["responses"]

    assert "изменён" in result
    assert save_result is False
    assert responses == [
        "Проект развивается",
        "Работа продолжается",
    ]
    assert read_document(
        isolated_knowledge
    )["_meta"]["version"] == "v002"


def test_cancel_answer_change(
    isolated_knowledge,
) -> None:
    """Отмена оставляет прежний ответ."""

    get_response(
        "измени ответ категории project: "
        "Новый ответ"
    )
    result, _ = get_response("отмена")

    assert "отменена" in result
    assert read_document(
        isolated_knowledge
    )["intents"][0]["responses"][0] == (
        "Мы развиваем Giperion"
    )


def test_remove_phrase_requires_confirmation(
    isolated_knowledge,
) -> None:
    """После подтверждения удаляется только выбранная фраза."""

    request, _ = get_response(
        "удали фразу из категории project: "
        "как идет проект"
    )

    assert "подтверждаю" in request
    assert len(
        read_document(
            isolated_knowledge
        )["intents"][0]["patterns"]
    ) == 2

    result, save_result = get_response(
        "подтверждаю"
    )

    assert "Фраза удалена" in result
    assert save_result is False
    assert read_document(
        isolated_knowledge
    )["intents"][0]["patterns"] == [
        "что нового в проекте"
    ]


def test_cannot_remove_only_phrase(
    isolated_knowledge,
) -> None:
    """Единственная фраза категории не удаляется."""

    document = read_document(isolated_knowledge)
    document["intents"][0]["patterns"] = [
        "как идет проект"
    ]

    isolated_knowledge[
        "intents_file"
    ].write_text(
        json.dumps(
            document,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result, save_to_history = get_response(
        "удали фразу из категории project: "
        "как идет проект"
    )

    assert "единственную фразу" in result
    assert save_to_history is False
    assert read_document(
        isolated_knowledge
    )["intents"][0]["patterns"] == [
        "как идет проект"
    ]


def test_remove_category_requires_confirmation(
    isolated_knowledge,
) -> None:
    """Категория удаляется только после подтверждения."""

    request, _ = get_response(
        "удали категорию project"
    )

    assert "подтверждаю" in request
    assert len(
        read_document(
            isolated_knowledge
        )["intents"]
    ) == 1

    result, save_result = get_response(
        "подтверждаю"
    )

    assert "удалена" in result
    assert save_result is False
    assert read_document(
        isolated_knowledge
    )["intents"] == []
    assert read_document(
        isolated_knowledge
    )["_meta"]["version"] == "v002"


def test_cancel_category_removal(
    isolated_knowledge,
) -> None:
    """Отмена сохраняет категорию."""

    get_response(
        "удали категорию project"
    )
    result, _ = get_response(
        "отмена"
    )

    assert "отменена" in result
    assert len(
        read_document(
            isolated_knowledge
        )["intents"]
    ) == 1


def test_log_excludes_phrase_and_answer(
    isolated_knowledge,
) -> None:
    """Журнал не содержит текст удалённой фразы или нового ответа."""

    get_response(
        "измени ответ категории project: "
        "Секретный ответ"
    )
    get_response("подтверждаю")

    get_response(
        "удали фразу из категории project: "
        "как идет проект"
    )
    get_response("подтверждаю")

    log_text = isolated_knowledge[
        "log_file"
    ].read_text(
        encoding="utf-8"
    )

    assert "project" in log_text
    assert "Секретный ответ" not in log_text
    assert "как идет проект" not in log_text
