# Giperion/tests/test_learning.py                                 v001
# Проверки обучения Giperion новым фразам.
# Последнее изменение: добавлены изолированные тесты категорий, повторов и записи обучения.

import json

import pytest
from giperion_model._shared import action_log as model_action_log
from giperion_model.language import (
    intent_handler,
    learning_service,
)

from shared import action_log
from terminal.core.chatbot import get_response


@pytest.fixture
def isolated_learning(
    tmp_path,
    monkeypatch,
):
    """Подменяет файл намерений и журнал временными файлами."""

    intents_file = (
        tmp_path / "intents.json"
    )
    log_file = (
        tmp_path / "logs" / "actions.log"
    )

    intents_file.write_text(
        json.dumps(
            [
                {
                    "tag": "greeting",
                    "patterns": ["привет"],
                    "responses": ["Здравствуй!"],
                },
                {
                    "tag": "thanks",
                    "patterns": ["спасибо"],
                    "responses": ["Пожалуйста!"],
                },
            ],
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
    monkeypatch.setattr(
        model_action_log,
        "LOG_FILE",
        log_file,
    )

    return {
        "intents_file": intents_file,
        "log_file": log_file,
    }


def test_show_categories_is_system_command(
    isolated_learning,
) -> None:
    """Просмотр категорий не сохраняется в истории."""

    response, save_to_history = get_response(
        "покажи категории"
    )

    assert "greeting" in response
    assert "thanks" in response
    assert save_to_history is False


def test_learned_phrase_is_recognized(
    isolated_learning,
) -> None:
    """После обучения новая фраза распознаётся как намерение."""

    learning_response, save_learning = get_response(
        "научи фразе: добрый день, друг; "
        "категория: greeting"
    )
    dialogue_response, save_dialogue = get_response(
        "добрый день, друг"
    )

    assert "Фраза добавлена" in learning_response
    assert save_learning is False
    assert dialogue_response == "Здравствуй!"
    assert save_dialogue is True

    document = json.loads(
        isolated_learning["intents_file"].read_text(
            encoding="utf-8"
        )
    )

    assert (
        "добрый день, друг"
        in document[0]["patterns"]
    )


def test_duplicate_phrase_is_not_added(
    isolated_learning,
) -> None:
    """Существующая фраза не добавляется повторно."""

    response, save_to_history = get_response(
        "научи фразе: привет; "
        "категория: greeting"
    )

    document = json.loads(
        isolated_learning["intents_file"].read_text(
            encoding="utf-8"
        )
    )

    assert "уже есть" in response
    assert save_to_history is False
    assert document[0]["patterns"] == ["привет"]
    assert not isolated_learning["log_file"].exists()


def test_unknown_category_does_not_change_file(
    isolated_learning,
) -> None:
    """Неизвестная категория не изменяет intents.json."""

    original_text = isolated_learning[
        "intents_file"
    ].read_text(encoding="utf-8")

    response, save_to_history = get_response(
        "научи фразе: хорошего дня; "
        "категория: missing"
    )

    assert "не найдена" in response
    assert save_to_history is False
    assert (
        isolated_learning["intents_file"]
        .read_text(encoding="utf-8")
        == original_text
    )


def test_learning_log_excludes_phrase(
    isolated_learning,
) -> None:
    """В журнале есть категория, но нет текста выученной фразы."""

    get_response(
        "научи фразе: уникальная учебная фраза; "
        "категория: greeting"
    )

    log_text = isolated_learning[
        "log_file"
    ].read_text(encoding="utf-8")

    assert "greeting" in log_text
    assert "уникальная учебная фраза" not in log_text


def test_document_with_intents_key_is_preserved(
    isolated_learning,
) -> None:
    """Обучение сохраняет формат документа с ключом intents."""

    intents_file = isolated_learning["intents_file"]

    intents_file.write_text(
        json.dumps(
            {
                "version": 1,
                "intents": [
                    {
                        "tag": "greeting",
                        "patterns": ["привет"],
                        "responses": ["Здравствуй!"],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    response, _ = get_response(
        "научи фразе: приветствую; "
        "категория: greeting"
    )

    document = json.loads(
        intents_file.read_text(
            encoding="utf-8"
        )
    )

    assert "Фраза добавлена" in response
    assert document["version"] == 1
    assert (
        "приветствую"
        in document["intents"][0]["patterns"]
    )
