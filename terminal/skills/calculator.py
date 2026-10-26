# Giperion/app/skills/calculator.py                               v001
# Безопасное вычисление арифметических выражений Giperion.
# Последнее изменение: файл перемещён в пакет skills без изменения логики.

import ast
import operator

MAX_POWER = 1000
MAX_RESULT_BITS = 20_000

ALLOWED_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

ALLOWED_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculate_expression(expression: str) -> int | float:
    """Безопасно вычисляет арифметическое выражение."""

    parsed_expression = ast.parse(
        expression,
        mode="eval",
    )

    return evaluate_node(parsed_expression.body)


def evaluate_node(node: ast.AST) -> int | float:
    """Рекурсивно вычисляет разрешённые узлы арифметического выражения."""

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise ValueError("Логические значения не поддерживаются.")

        if isinstance(node.value, (int, float)):
            return node.value

        raise ValueError("Разрешены только числа.")

    if isinstance(node, ast.BinOp):
        operator_type = type(node.op)

        if operator_type not in ALLOWED_BINARY_OPERATORS:
            raise ValueError("Этот оператор не поддерживается.")

        left_value = evaluate_node(node.left)
        right_value = evaluate_node(node.right)

        if operator_type is ast.Pow:
            try:
                exponent = float(right_value)
            except OverflowError as error:
                raise ValueError(
                    "Степень слишком большая."
                ) from error

            if abs(exponent) > MAX_POWER:
                raise ValueError(
                    "Степень слишком большая."
                )

            result = left_value ** right_value

            if (
                isinstance(result, int)
                and result.bit_length() > MAX_RESULT_BITS
            ):
                raise ValueError(
                    "Результат степени слишком большой."
                )

            return result

        return ALLOWED_BINARY_OPERATORS[operator_type](
            left_value,
            right_value,
        )

    if isinstance(node, ast.UnaryOp):
        operator_type = type(node.op)

        if operator_type not in ALLOWED_UNARY_OPERATORS:
            raise ValueError("Этот оператор не поддерживается.")

        operand_value = evaluate_node(node.operand)

        return ALLOWED_UNARY_OPERATORS[operator_type](
            operand_value
        )

    raise ValueError("Выражение содержит недопустимые элементы.")