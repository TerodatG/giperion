# GiperionModel/tests/test_language_guards.py                        v001
# Краевые случаи языковых модулей.

from giperion_model.language.learning_presenter import (
    get_categories_response,
)
from giperion_model.personality_catalog import get_personality


def test_empty_categories_response_is_safe() -> None:
    """Пустой список категорий не должен падать на max()."""

    assert "нет категорий" in get_categories_response([])


def test_empty_matrices_are_respected() -> None:
    """Явно пустой список матриц не означает «загрузи с диска»."""

    assert get_personality("writer", []) is None
