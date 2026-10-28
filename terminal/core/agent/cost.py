# Giperion/terminal/core/agent/cost.py                                 v001
# Оценка стоимости запроса по расходу токенов.

# Цены за миллион токенов: (вход, выход). Значения примерные,
# нужны для ориентира в интерфейсе, а не для бухгалтерии.
PRICES = {
    "claude-opus": (15.0, 75.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (0.8, 4.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4.1": (2.0, 8.0),
    "deepseek": (0.27, 1.1),
    "qwen": (0.2, 0.6),
    "llama": (0.0, 0.0),
    "local": (0.0, 0.0),
}

# Если модель неизвестна, считаем бесплатной (локальные модели).
DEFAULT_PRICE = (0.0, 0.0)


def price_for(model: str) -> tuple[float, float]:
    """Цена модели: сначала точное совпадение, затем по началу имени."""

    name = str(model or "").strip().lower()

    if not name:
        return DEFAULT_PRICE

    if name in PRICES:
        return PRICES[name]

    for key, value in PRICES.items():
        if name.startswith(key) or key in name:
            return value

    return DEFAULT_PRICE


def estimate_cost(model: str, usage: dict | None) -> float:
    """Стоимость запроса в долларах по расходу токенов."""

    if not usage:
        return 0.0

    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    price_in, price_out = price_for(model)

    return (
        prompt * price_in + completion * price_out
    ) / 1_000_000


def format_cost(value: float) -> str:
    """Короткая запись суммы: $0.0123 или $1.20."""

    if value <= 0:
        return "$0"

    if value < 0.01:
        return f"${value:.4f}"

    return f"${value:.2f}"


def format_usage(usage: dict | None) -> str:
    """Строка «токенов: вход / выход»."""

    if not usage:
        return "токенов нет"

    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)

    return f"токенов: {prompt} / {completion}"
