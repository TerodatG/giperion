# Giperion/tests/test_agent_alerts.py                                   v001
# Алерты: доля успеха, порог и вебхук.

from terminal.core.agent import alerts


def test_summary_counts_failures() -> None:
    """Сводка считает успех и последнюю ошибку."""

    stats = alerts.summary(
        [
            {"ok": True},
            {"ok": False, "error": "сбой"},
            {"ok": True},
        ]
    )

    assert stats["total"] == 3
    assert stats["ok"] == 2
    assert stats["failed"] == 1
    assert stats["last_error"] == "сбой"
    assert abs(stats["rate"] - 2 / 3) < 1e-9


def test_threshold() -> None:
    """Порог сравнивается с долей успеха."""

    assert alerts.needs_alert({"total": 3, "rate": 0.3}, 0.5)
    assert not alerts.needs_alert({"total": 3, "rate": 0.8}, 0.5)
    assert not alerts.needs_alert({"total": 0, "rate": 0.0}, 0.5)


def test_check_sends_only_on_alert(monkeypatch) -> None:
    """Вебхук вызывается только при падении ниже порога."""

    sent = []
    monkeypatch.setattr(
        alerts.notify,
        "send",
        lambda text, url="": sent.append((text, url)) or True,
    )

    stats, alert = alerts.check(
        [{"ok": False, "error": "bad"}],
        threshold=0.5,
        url="https://example.com/hook",
    )

    assert alert
    assert stats["failed"] == 1
    assert sent and sent[0][1] == "https://example.com/hook"

    sent.clear()

    _stats, alert = alerts.check(
        [{"ok": True}],
        threshold=0.5,
    )

    assert not alert
    assert sent == []
