# Giperion/tests/test_calculator.py                               v002
# Автоматические тесты безопасного калькулятора Giperion.
# Последнее изменение: обновлены импорты после переноса calculator в пакет skills.

import pytest

from app.skills.calculator import calculate_expression


def test_calculate_addition() -> None:
    """Проверяет сложение чисел."""

    assert calculate_expression("2 + 3") == 5


def test_calculate_brackets() -> None:
    """Проверяет вычисление выражения со скобками."""

    assert calculate_expression("(2 + 3) * 4") == 20


def test_calculate_power() -> None:
    """Проверяет возведение числа в степень."""

    assert calculate_expression("2 ** 3") == 8


def test_calculator_rejects_function_call() -> None:
    """Проверяет запрет выполнения функций из выражения."""

    with pytest.raises(ValueError):
        calculate_expression("__import__('os').system('dir')")