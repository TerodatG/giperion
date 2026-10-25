# Giperion/terminal/core/agent/budget.py                              v001
# Бюджет задачи: лимиты токенов и стоимости и оценка расхода.

from dataclasses import dataclass

MILLION = 1_000_000.0


@dataclass(frozen=True)
class BudgetLimits:
    """Лимиты задачи и цены провайдера за миллион токенов в долларах."""

    tokens: int = 0
    cost: float = 0.0
    price_in: float = 0.0
    price_out: float = 0.0

    @property
    def enabled(self) -> bool:
        """Задан ли хотя бы один лимит."""

        return self.tokens > 0 or self.cost > 0

    @property
    def priced(self) -> bool:
        """Есть ли из чего считать стоимость."""

        return self.price_in > 0 or self.price_out > 0


def cost_of(
    prompt_tokens: int,
    completion_tokens: int,
    limits: BudgetLimits,
) -> float:
    """Стоимость запроса в долларах по ценам за миллион токенов."""

    prompt = max(0, int(prompt_tokens))
    completion = max(0, int(completion_tokens))

    return (
        prompt * limits.price_in + completion * limits.price_out
    ) / MILLION


def exceeded(limits: BudgetLimits, tokens: int, cost: float) -> str:
    """Причина остановки или пустая строка, если бюджет в порядке."""

    if limits.tokens > 0 and tokens >= limits.tokens:
        return (
            f"Израсходован бюджет токенов: {tokens} из {limits.tokens}."
        )

    if limits.cost > 0 and cost >= limits.cost:
        return (
            "Израсходован бюджет стоимости: "
            f"${cost:.4f} из ${limits.cost:.2f}."
        )

    return ""


def describe(limits: BudgetLimits) -> str:
    """Короткое описание бюджета для окна и журнала."""

    parts = []

    if limits.tokens > 0:
        parts.append(f"{limits.tokens} токенов")

    if limits.cost > 0:
        parts.append(f"${limits.cost:.2f}")

    return " · ".join(parts) if parts else "без лимита"
