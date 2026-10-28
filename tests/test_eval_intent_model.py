# Giperion/tests/test_eval_intent_model.py                            v002
# Проверка метрик оценки интентов и локального порога качества.
# Последнее изменение: оценка только роутера.

import pytest

from giperion_model.language.linear_intent import LINEAR_MODEL_FILE
from tools.eval_intent_model import (
    main,
    parse_args,
)
from tools.intent_metrics import (
    bootstrap_metrics,
    class_metrics,
    macro_f1,
    percentile,
    selective_metrics,
)


def test_class_metrics_counts_precision_recall_f1() -> None:
    """Метрики класса считаются по обычным формулам."""

    metrics = class_metrics(
        ["a", "a", "b", "b"],
        ["a", "b", "b", "b"],
    )

    assert metrics["a"]["precision"] == 1.0
    assert metrics["a"]["recall"] == 0.5
    assert metrics["a"]["f1"] == pytest.approx(2 / 3)
    assert metrics["b"]["precision"] == pytest.approx(2 / 3)
    assert metrics["b"]["recall"] == 1.0
    assert metrics["b"]["support"] == 2.0


def test_macro_f1_weighs_classes_equally() -> None:
    """Редкий класс весит столько же, сколько частый."""

    truths = ["rare"] + ["often"] * 9
    predictions = ["rare"] + ["often"] * 8 + ["rare"]

    metrics = class_metrics(truths, predictions)

    assert macro_f1(metrics) == pytest.approx(
        (metrics["rare"]["f1"] + metrics["often"]["f1"]) / 2
    )
    assert macro_f1({}) == 0.0


def test_selective_metrics_drops_low_confidence() -> None:
    """Покрытие считает только ответы выше порога."""

    coverage, accuracy = selective_metrics(
        ["a", "b", "c", "d"],
        ["a", "b", "c", "x"],
        [0.9, 0.2, 0.5, 0.8],
        0.45,
    )

    assert coverage == pytest.approx(0.75)
    assert accuracy == pytest.approx(2 / 3)


def test_selective_metrics_without_answers() -> None:
    """Если порог никто не прошёл, метрики нулевые."""

    assert selective_metrics(
        ["a"],
        ["a"],
        [0.1],
        0.45,
    ) == (0.0, 0.0)


def test_router_gate_thresholds() -> None:
    """Гейт роутера требует 0.75 top-1 и 0.70 macro-F1."""

    assert parse_args([]).min_top1 == 0.75
    assert parse_args(["--router"]).min_top1 == 0.75
    assert parse_args([]).min_macro_f1 == 0.70
    assert parse_args(["--router"]).min_macro_f1 == 0.70


def test_bootstrap_perfect_predictions() -> None:
    """Идеальные ответы дают интервал из единиц."""

    interval = bootstrap_metrics(
        ["a", "b", "a", "b"],
        ["a", "b", "a", "b"],
        iterations=50,
    )

    assert interval["top1_low"] == 1.0
    assert interval["top1_high"] == 1.0
    assert interval["macro_low"] == 1.0
    assert interval["macro_high"] == 1.0


def test_bootstrap_interval_contains_point() -> None:
    """Доверительный интервал накрывает точечную оценку."""

    truths = ["a", "a", "b", "b", "c", "c"]
    predictions = ["a", "b", "b", "b", "c", "a"]
    interval = bootstrap_metrics(
        truths,
        predictions,
        iterations=200,
    )
    metrics = class_metrics(truths, predictions)
    point = macro_f1(metrics)

    assert interval["macro_low"] <= point <= interval["macro_high"]
    assert interval["top1_low"] <= 0.5 <= interval["top1_high"]


def test_percentile_edges() -> None:
    """Процентили не выходят за границы списка."""

    assert percentile([1.0, 2.0, 3.0], 0.0) == 1.0
    assert percentile([1.0, 2.0, 3.0], 1.0) == 3.0


@pytest.mark.skipif(
    not LINEAR_MODEL_FILE.is_file(),
    reason="нет обученного линейного роутера",
)
def test_linear_router_passes_quality_gate() -> None:
    """Линейный роутер не должен проседать ниже порогов."""

    assert main(["--router", "--fail"]) == 0
