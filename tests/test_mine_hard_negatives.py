# Giperion/tests/test_mine_hard_negatives.py                          v001
# Отчёт по сложным парам намерений.
# Последнее изменение: первый вариант — ранжирование путаниц.

from tools.mine_hard_negatives import build_report, rank_confusions


def test_rank_confusions_sorts_by_count() -> None:
    """Частые пары идут первыми, при равенстве — по алфавиту."""

    ranked = rank_confusions(
        [
            ("b", "a"),
            ("a", "b"),
            ("a", "b"),
            ("c", "d"),
        ]
    )

    assert ranked[0] == (("a", "b"), 2)
    assert ranked[1] == (("b", "a"), 1)
    assert ranked[2] == (("c", "d"), 1)


def test_report_keeps_examples() -> None:
    """В отчёт попадают примеры ошибок выбранной пары."""

    errors = [
        {
            "text": "пример",
            "true": "a",
            "predicted": "b",
            "confidence": 0.4,
        },
        {
            "text": "другой",
            "true": "c",
            "predicted": "d",
            "confidence": 0.3,
        },
    ]
    report = build_report(
        errors,
        [("a", "b"), ("c", "d")],
        top=1,
        examples=1,
    )

    assert report["errors"] == 2
    assert len(report["confusions"]) == 1
    assert report["confusions"][0]["examples"][0]["text"] == "пример"
