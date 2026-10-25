# Giperion/tests/test_category_creation.py                       v001
# Проверки создания новых категорий через терминальные команды.
# Последнее изменение: добавлены тесты подтверждения, отмены и сохранения ответа.

import json

import pytest

from giperion.language import (
    intent_handler,
    learning_service,
)
from shared import action_log
from terminal.core.chatbot import get_response
from terminal.memory import system_handler


@pytest.fixture
def isolated_categories(
    tmp_path,
    monkeypatch,
):
    """Направляет обучающие данные и журнал во временную папку."""

    intents_file = (
        tmp_path
        / "intents.json"
    )
    log_file = (
        tmp_path
        / "logs"
        / "actions.log"
    )

    initial_intents = [
        {
            "tag": "greeting",
            "patterns": [
                "привет"
            ],
            "responses": [
                "Здравствуй!"
            ],
        }
    ]

    intents_file.write_text(
        json.dumps(
            initial_intents,
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


def get_saved_intents(
    isolated_categories,
) -> list[dict]:
    """Читает временный файл намерений теста."""

    return json.loads(
        isolated_categories[
            "intents_file"
        ].read_text(
            encoding="utf-8"
        )
    )


def test_confirmation_creates_category(
    isolated_categories,
) -> None:
    """Категория создаётся только после подтверждения."""

    request, save_request = get_response(
        "создай категорию: project; "
        "фраза: Как идёт проект; "
        "ответ: Мы развиваем Giperion"
    )

    assert (
        "Для выполнения напиши: "
        "подтверждаю."
    ) in request
    assert save_request is False
    assert len(
        get_saved_intents(
            isolated_categories
        )
    ) == 1

    result, save_result = get_response(
        "подтверждаю"
    )

    intents = get_saved_intents(
        isolated_categories
    )

    assert result == (
        "Категория «project» создана."
    )
    assert save_result is False
    assert len(intents) == 2
    assert intents[1] == {
        "tag": "project",
        "patterns": [
            "Как идёт проект"
        ],
        "responses": [
            "Мы развиваем Giperion"
        ],
    }


def test_new_phrase_returns_saved_answer(
    isolated_categories,
) -> None:
    """Новая фраза возвращает ответ с исходным регистром."""

    get_response(
        "создай категорию: project; "
        "фраза: Как идёт проект; "
        "ответ: Мы развиваем Giperion"
    )
    get_response(
        "подтверждаю"
    )

    answer, save_to_history = (
        get_response(
            "как идёт проект"
        )
    )

    assert answer == (
        "Мы развиваем Giperion"
    )
    assert save_to_history is True


def test_cancel_does_not_create_category(
    isolated_categories,
) -> None:
    """Отмена оставляет intents.json без изменений."""

    original_text = (
        isolated_categories[
            "intents_file"
        ].read_text(
            encoding="utf-8"
        )
    )

    get_response(
        "создай категорию: project; "
        "фраза: Как идёт проект; "
        "ответ: Мы развиваем Giperion"
    )

    result, save_to_history = (
        get_response(
            "отмена"
        )
    )

    assert "отменена" in result
    assert save_to_history is False
    assert (
        isolated_categories[
            "intents_file"
        ].read_text(
            encoding="utf-8"
        )
        == original_text
    )


def test_existing_category_is_not_overwritten(
    isolated_categories,
) -> None:
    """Повторное название не заменяет старую категорию."""

    original_text = (
        isolated_categories[
            "intents_file"
        ].read_text(
            encoding="utf-8"
        )
    )

    result, save_to_history = (
        get_response(
            "создай категорию: greeting; "
            "фраза: Здравствуй, друг; "
            "ответ: Новый ответ"
        )
    )

    assert "уже существует" in result
    assert save_to_history is False
    assert (
        isolated_categories[
            "intents_file"
        ].read_text(
            encoding="utf-8"
        )
        == original_text
    )


def test_existing_phrase_is_not_copied(
    isolated_categories,
) -> None:
    """Фраза из другой категории не дублируется."""

    result, save_to_history = (
        get_response(
            "создай категорию: project; "
            "фраза: Привет; "
            "ответ: Новый ответ"
        )
    )

    assert "уже есть" in result
    assert save_to_history is False
    assert len(
        get_saved_intents(
            isolated_categories
        )
    ) == 1


def test_log_does_not_contain_phrase_or_answer(
    isolated_categories,
) -> None:
    """Журнал записывает название категории без текста обучения."""

    get_response(
        "создай категорию: project; "
        "фраза: Секретная фраза; "
        "ответ: Секретный ответ"
    )
    get_response(
        "подтверждаю"
    )

    log_text = (
        isolated_categories[
            "log_file"
        ].read_text(
            encoding="utf-8"
        )
    )

    assert (
        "Создана категория project"
    ) in log_text
    assert (
        "Секретная фраза"
        not in log_text
    )
    assert (
        "Секретный ответ"
        not in log_text
    )


def test_category_added_while_waiting_is_not_duplicated(
    isolated_categories,
) -> None:
    """При подтверждении категория проверяется ещё раз."""

    get_response(
        "создай категорию: project; "
        "фраза: Как идёт проект; "
        "ответ: Мы развиваем Giperion"
    )

    intents = get_saved_intents(
        isolated_categories
    )
    intents.append(
        {
            "tag": "project",
            "patterns": [
                "другая фраза"
            ],
            "responses": [
                "Другой ответ"
            ],
        }
    )

    isolated_categories[
        "intents_file"
    ].write_text(
        json.dumps(
            intents,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    result, save_to_history = (
        get_response(
            "подтверждаю"
        )
    )

    assert "уже существует" in result
    assert save_to_history is False
    assert len(
        get_saved_intents(
            isolated_categories
        )
    ) == 2
    assert not isolated_categories[
        "log_file"
    ].exists()
