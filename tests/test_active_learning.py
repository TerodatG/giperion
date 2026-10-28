# Giperion/tests/test_active_learning.py                              v001
# Сводка цикла активного обучения.
# Последнее изменение: первый вариант — подсчёт действий.

from tools.active_learning import summarize


def test_summary_counts_actions() -> None:
    """add/trash/skip считаются отдельно."""

    summary = summarize(
        [
            {"action": "add"},
            {"action": "add"},
            {"action": "trash"},
            {"action": "skip"},
        ]
    )

    assert summary == {
        "total": 4,
        "add": 2,
        "trash": 1,
        "skip": 1,
    }
