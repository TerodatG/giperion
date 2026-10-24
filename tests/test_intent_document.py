# Giperion/tests/test_intent_document.py                          v001
# Проверки чтения намерений из формата данных проекта Giperion.
# Последнее изменение: добавлены тесты объекта с _meta и ключом intents.

import json

import pytest

from giperion.language import intent_handler


@pytest.fixture
def isolated_intents(
    tmp_path,
    monkeypatch,
):
    """Создаёт временный файл намерений с метаданными."""

    intents_file = (
        tmp_path / "intents.json"
    )

    document = {
        "_meta": {
            "path": "Giperion/data/intents.json",
            "version": "v002",
        },
        "intents": [
            {
                "tag": "project",
                "patterns": [
                    "как идет проект"
                ],
                "responses": [
                    "Мы развиваем Giperion"
                ],
            }
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
        intent_handler,
        "INTENTS_FILE",
        intents_file,
    )

    return intents_file


def test_load_intents_from_document(
    isolated_intents,
) -> None:
    """Загружает категории из объекта с ключом intents."""

    intents = intent_handler.load_intents()

    assert len(intents) == 1
    assert intents[0]["tag"] == "project"


def test_find_project_response(
    isolated_intents,
) -> None:
    """Находит ответ из категории project."""

    response = (
        intent_handler.find_intent_response(
            "как идет проект"
        )
    )

    assert response == (
        "Мы развиваем Giperion"
    )


def test_find_project_response_with_spaces(
    isolated_intents,
) -> None:
    """Лишний пробел в конце не мешает найти ответ."""

    response = (
        intent_handler.find_intent_response(
            "как идет проект "
        )
    )

    assert response == (
        "Мы развиваем Giperion"
    )


def test_find_close_pattern_in_document(
    isolated_intents,
) -> None:
    """Ищет похожую фразу внутри объекта с намерениями."""

    pattern = (
        intent_handler.find_close_pattern(
            "как идет проек"
        )
    )

    assert pattern == (
        "как идет проект"
    )
