# Giperion/tests/test_eval_intent_model.py                            v001
# Проверка метрик оценки интентов и локального порога качества.
# Последнее изменение: первый вариант — macro-F1 и покрытие.

import pytest

from tools.eval_intent_model import (
    CLASSIFIER_FILE,
    class_metrics,
    macro_f1,
    main,
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


@pytest.mark.skipif(
    not CLASSIFIER_FILE.is_file(),
    reason="нет обученного чекпоинта",
)
def test_current_model_passes_quality_gate() -> None:
    """Текущая модель не должна проседать ниже порогов."""

    assert main(["--fail"]) == 0
