# Giperion/tools/intent_metrics.py                                  v001
# Метрики классификатора намерений и bootstrap-интервалы.
# Последнее изменение: вынесено из eval_intent_model.

import random
from collections import Counter


def class_metrics(
    truths: list[str],
    predictions: list[str],
) -> dict[str, dict[str, float]]:
    """Считает precision, recall и F1 для каждого класса."""

    pairs = list(zip(truths, predictions, strict=False))
    result: dict[str, dict[str, float]] = {}

    for label in sorted(set(truths)):
        true_positive = sum(
            1
            for truth, predicted in pairs
            if truth == label and predicted == label
        )
        predicted_positive = sum(
            1 for _truth, predicted in pairs if predicted == label
        )
        actual_positive = sum(
            1 for truth, _predicted in pairs if truth == label
        )

        precision = (
            true_positive / predicted_positive
            if predicted_positive
            else 0.0
        )
        recall = (
            true_positive / actual_positive
            if actual_positive
            else 0.0
        )
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

        result[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": float(actual_positive),
        }

    return result


def macro_f1(per_class: dict[str, dict[str, float]]) -> float:
    """Средний F1 по классам: редкие классы весят как частые."""

    if not per_class:
        return 0.0

    return sum(item["f1"] for item in per_class.values()) / len(
        per_class
    )


def selective_metrics(
    truths: list[str],
    predictions: list[str],
    confidences: list[float],
    threshold: float,
) -> tuple[float, float]:
    """Покрытие и точность на ответах не ниже порога."""

    covered = [
        (truth, predicted)
        for truth, predicted, confidence in zip(
            truths,
            predictions,
            confidences,
            strict=False,
        )
        if confidence >= threshold
    ]

    if not covered:
        return 0.0, 0.0

    correct = sum(
        1 for truth, predicted in covered if truth == predicted
    )

    return len(covered) / len(truths), correct / len(covered)


def macro_f1_from_counts(
    pair_counts: Counter,
    true_counts: Counter,
    predicted_counts: Counter,
    labels: list[int],
) -> float:
    """Считает macro-F1 по счётчикам одного bootstrap-сэмпла."""

    scores = []

    for label in labels:
        actual = true_counts[label]

        if actual == 0:
            continue

        true_positive = pair_counts[(label, label)]
        predicted = predicted_counts[label]
        precision = true_positive / predicted if predicted else 0.0
        recall = true_positive / actual
        scores.append(
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

    return sum(scores) / len(scores) if scores else 0.0


def percentile(values: list[float], fraction: float) -> float:
    """Процентиль без интерполяции: достаточно для отчёта."""

    ordered = sorted(values)
    index = int(fraction * (len(ordered) - 1))

    return ordered[max(0, min(index, len(ordered) - 1))]


def calibration_metrics(
    confidences: list[float],
    correct: list[bool],
    bins: int = 10,
) -> tuple[float, float]:
    """Возвращает ECE и Brier score для уверенности модели."""

    if not confidences:
        return 0.0, 0.0

    if len(confidences) != len(correct):
        raise ValueError("confidences и correct разной длины")

    brier = sum(
        (confidence - int(is_correct)) ** 2
        for confidence, is_correct in zip(
            confidences,
            correct,
            strict=False,
        )
    ) / len(confidences)
    buckets = [[] for _ in range(bins)]

    for confidence, is_correct in zip(
        confidences,
        correct,
        strict=False,
    ):
        index = min(int(confidence * bins), bins - 1)
        buckets[index].append((confidence, is_correct))

    ece = 0.0

    for bucket in buckets:
        if not bucket:
            continue

        average_confidence = sum(
            item[0] for item in bucket
        ) / len(bucket)
        accuracy = sum(
            int(item[1]) for item in bucket
        ) / len(bucket)
        ece += (
            len(bucket)
            / len(confidences)
            * abs(average_confidence - accuracy)
        )

    return ece, brier


def bootstrap_metrics(
    truths: list[str],
    predictions: list[str],
    iterations: int = 1000,
    seed: int = 42,
) -> dict[str, float]:
    """Считает 95% доверительные интервалы top-1 и macro-F1."""

    labels = sorted(set(truths))
    indexes = {label: index for index, label in enumerate(labels)}
    true_ids = [indexes[label] for label in truths]
    predicted_ids = [
        indexes.get(label, -1) for label in predictions
    ]
    rng = random.Random(seed)
    size = len(truths)
    top1_values = []
    f1_values = []

    for _ in range(iterations):
        sample = rng.choices(range(size), k=size)
        pair_counts: Counter = Counter()
        true_counts: Counter = Counter()
        predicted_counts: Counter = Counter()
        correct = 0

        for position in sample:
            truth = true_ids[position]
            predicted = predicted_ids[position]
            pair_counts[(truth, predicted)] += 1
            true_counts[truth] += 1
            predicted_counts[predicted] += 1

            if truth == predicted:
                correct += 1

        top1_values.append(correct / size)
        f1_values.append(
            macro_f1_from_counts(
                pair_counts,
                true_counts,
                predicted_counts,
                list(range(len(labels))),
            )
        )

    return {
        "top1_low": percentile(top1_values, 0.025),
        "top1_high": percentile(top1_values, 0.975),
        "macro_low": percentile(f1_values, 0.025),
        "macro_high": percentile(f1_values, 0.975),
    }
