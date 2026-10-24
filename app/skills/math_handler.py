# Giperion/app/skills/math_handler.py                             v001
# Обработка математических выражений и временных переменных Giperion.
# Последнее изменение: файл перемещён в пакет skills и обновлены импорты.

import re

from app.skills.calculator import calculate_expression

variables: dict[str, int | float] = {}

VARIABLE_NAME_PATTERN = re.compile(
    r"^[a-zA-Z_][a-zA-Z0-9_]*$"
)


def format_number(number: int | float) -> str:
    """Преобразует число в удобный текстовый вид."""

    if isinstance(number, float) and number.is_integer():
        return str(int(number))

    return str(number)


def replace_variables(expression: str) -> str:
    """Подставляет значения временных переменных в выражение."""

    for name, value in variables.items():
        expression = re.sub(
            rf"\b{re.escape(name)}\b",
            str(value),
            expression,
        )

    return expression


def get_math_response(message: str) -> str | None:
    """Пытается вычислить выражение или сохранить переменную."""

    expression = message.replace(",", ".").strip()

    assignment_match = re.fullmatch(
        r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)",
        expression,
    )

    if assignment_match:
        variable_name = assignment_match.group(1)
        variable_expression = assignment_match.group(2)

        try:
            result = calculate_expression(
                replace_variables(variable_expression)
            )
        except (
            SyntaxError,
            ValueError,
            ZeroDivisionError,
        ):
            return "Не удалось вычислить значение переменной."

        variables[variable_name] = result

        return (
            f"Переменная {variable_name} сохранена: "
            f"{format_number(result)}."
        )

    if not re.fullmatch(
        r"[0-9a-zA-Z_+\-*/().\s%]+",
        expression,
    ):
        return None

    if not any(
        symbol in expression
        for symbol in "+-*/%"
    ):
        return None

    try:
        result = calculate_expression(
            replace_variables(expression)
        )
    except (
        SyntaxError,
        ValueError,
        ZeroDivisionError,
    ):
        return "Не удалось вычислить выражение."

    return f"Результат: {format_number(result)}."


def get_variables_response() -> str:
    """Возвращает список временных переменных калькулятора."""

    if not variables:
        return "Переменных пока нет."

    lines = ["Переменные:"]

    for name, value in sorted(variables.items()):
        lines.append(f"{name} = {format_number(value)}")

    return "\n".join(lines)


def clear_variables_response() -> str:
    """Очищает временные переменные калькулятора."""

    variables.clear()

    return "Временные переменные очищены."