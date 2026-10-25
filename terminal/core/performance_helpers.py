# Giperion/terminal/core/performance_helpers.py                       v001
# Мелкие помощники счётчиков.
# Последнее изменение: вынесено из performance_monitor.

_GHOST_INTERFACES = ("loopback", "isatap", "teredo", "pseudo")


def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 100.0,
) -> float:
    """Ограничивает показатель разумными рамками."""

    return max(low, min(high, float(value)))


def _sum_filtered(
    values: list[tuple[str, float]],
    contains: str = "",
) -> float:
    """Суммирует значения экземпляров, отбрасывая служебные."""

    total = 0.0

    for name, value in values:
        lowered = name.lower()

        if contains and contains not in lowered:
            continue

        if any(ghost in lowered for ghost in _GHOST_INTERFACES):
            continue

        total += value

    return total
