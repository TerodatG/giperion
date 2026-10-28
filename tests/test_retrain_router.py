# Giperion/tests/test_retrain_router.py                               v001
# Правило продвижения нового артефакта роутера.
# Последнее изменение: первый вариант — Pareto-сравнение.

from tools.retrain_router import is_better


def test_candidate_with_both_metrics_better_wins() -> None:
    """Рост обеих метрик — продвижение."""

    assert is_better(
        {"eval_top1": 0.88, "eval_macro_f1": 0.89},
        {"eval_top1": 0.87, "eval_macro_f1": 0.88},
    )


def test_regression_blocks_promotion() -> None:
    """Худшая метрика не даёт заменить артефакт."""

    assert not is_better(
        {"eval_top1": 0.88, "eval_macro_f1": 0.86},
        {"eval_top1": 0.87, "eval_macro_f1": 0.88},
    )


def test_equal_metrics_do_not_promote() -> None:
    """Равные метрики не считаются улучшением."""

    assert not is_better(
        {"eval_top1": 0.87, "eval_macro_f1": 0.88},
        {"eval_top1": 0.87, "eval_macro_f1": 0.88},
    )


def test_missing_current_always_promotes() -> None:
    """Первый артефакт сохраняется всегда."""

    assert is_better({"eval_top1": 0.1}, {})
