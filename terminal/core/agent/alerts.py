# Giperion/terminal/core/agent/alerts.py                               v001
# Алерты по последним прогонам: доля успеха и вебхук.
# Последнее изменение: первый вариант — summary/needs_alert.

from terminal.core.agent import notify


def summary(runs: list[dict], window: int = 20) -> dict:
    """Считает успех по последним window прогонам."""

    sample = list(runs)[-max(1, int(window)):]
    total = len(sample)
    good = sum(1 for item in sample if item.get("ok") is True)
    rate = good / total if total else 1.0
    errors = [
        str(item.get("error") or "")
        for item in sample
        if item.get("ok") is not True and item.get("error")
    ]

    return {
        "total": total,
        "ok": good,
        "failed": total - good,
        "rate": rate,
        "last_error": errors[-1] if errors else "",
    }


def needs_alert(stats: dict, threshold: float = 0.5) -> bool:
    """Достаточно ли падений для тревоги."""

    return bool(stats.get("total")) and (
        float(stats.get("rate") or 0.0) < float(threshold)
    )


def check(
    runs: list[dict],
    threshold: float = 0.5,
    window: int = 20,
    url: str = "",
) -> tuple[dict, bool]:
    """Считает сводку и отправляет вебхук при необходимости."""

    stats = summary(runs, window)
    alert = needs_alert(stats, threshold)

    if alert:
        notify.send(
            "Giperion: успех "
            f"{stats['ok']}/{stats['total']} "
            f"({stats['rate']:.0%}), порог {threshold:.0%}. "
            f"Последняя ошибка: {stats['last_error'][:200]}",
            url,
        )

    return stats, alert
