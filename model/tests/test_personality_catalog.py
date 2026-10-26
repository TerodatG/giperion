# Giperion/tests/test_personality_catalog.py                       v001
# Проверки каталога личностных матриц и сохранённого выбора.

import json

from giperion_model.personality_catalog import (
    get_personality,
    get_selected_personality_id,
    load_personality_matrices,
    set_selected_personality_id,
)


def test_catalog_has_future_matrices() -> None:
    """В каталоге есть примеры поведения и заполненные карточки."""

    matrices = load_personality_matrices()

    assert len(matrices) >= 5

    names = {matrix["name"] for matrix in matrices}

    assert {"Хакер", "Военный", "Писатель", "Мудрец", "Гопник"} <= names

    for matrix in matrices:
        assert matrix["id"]
        assert matrix["name"]
        assert matrix["role"]
        assert matrix["motto"]
        assert matrix["description"]
        assert matrix["traits"]
        assert all(0 <= score <= 5 for score in matrix["traits"].values())


def test_get_personality_by_id() -> None:
    """Матрица находится по идентификатору."""

    matrix = get_personality("writer")

    assert matrix is not None
    assert matrix["name"] == "Писатель"


def test_default_selection_is_known() -> None:
    """По умолчанию выбирается существующая матрица."""

    known_ids = {
        matrix["id"]
        for matrix in load_personality_matrices()
    }

    assert get_selected_personality_id() in known_ids


def test_selection_round_trip(tmp_path) -> None:
    """Выбор сохраняется и читается из отдельного файла."""

    settings = tmp_path / "personality_settings.json"

    assert set_selected_personality_id("hacker", settings)
    assert get_selected_personality_id(settings) == "hacker"


def test_unknown_selection_falls_back(tmp_path) -> None:
    """Неизвестный идентификатор заменяется первой матрицей."""

    settings = tmp_path / "personality_settings.json"
    settings.write_text(
        json.dumps({"selected": "missing"}, ensure_ascii=False),
        encoding="utf-8",
    )

    matrices = load_personality_matrices()
    expected = matrices[0]["id"] if matrices else ""

    assert get_selected_personality_id(settings) == expected
