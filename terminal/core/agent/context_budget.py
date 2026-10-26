# Giperion/terminal/core/agent/context_budget.py                       v001
# Бюджет промпта из окна модели: токены → символы с запасом на ответ.
# Последнее изменение: первый вариант — каталог моделей и ручной fallback.

CHARS_PER_TOKEN = 2.5
OUTPUT_RESERVE = 0.25
MIN_CHARS = 8_000
MAX_CHARS = 2_000_000
THOUSANDS_LIMIT = 2_000


def normalize_tokens(value) -> int:
    """ Приводит значение context_limit к токенам.

    В каталоге встречаются оба вида: 200000 (токены) и 32 (тысячи).
    Значения меньше 2000 считаем тысячами.
    """

    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0

    if number <= 0:
        return 0

    if number < THOUSANDS_LIMIT:
        number *= 1_000

    return number


def budget_for_tokens(tokens: int) -> int:
    """Сколько символов промпта оставить при таком окне."""

    if tokens <= 0:
        return 0

    chars = int(tokens * CHARS_PER_TOKEN * (1 - OUTPUT_RESERVE))

    return min(MAX_CHARS, max(MIN_CHARS, chars))


def budget_for_model(model: dict | None, fallback: int) -> int:
    """Бюджет по контексту модели или ручное значение."""

    if not isinstance(model, dict):
        return int(fallback)

    tokens = normalize_tokens(model.get("context_limit"))

    if not tokens:
        return int(fallback)

    return budget_for_tokens(tokens)
