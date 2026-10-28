# Giperion/tools/router_artifact.py                                   v001
# Экспорт и измерение артефакта линейного роутера.
# Последнее изменение: вынесено из train_linear_intent.

import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from kraper_model.language.linear_intent import LinearIntentRouter
from tools.intent_metrics import (
    bootstrap_metrics,
    calibration_metrics,
    class_metrics,
    macro_f1,
)

NGRAM_RANGE = (3, 5)


def file_sha256(path: Path) -> str:
    """Считает хеш файла для метаданных артефакта."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


def measure_artifact(
    path: Path,
    texts: list[str],
    labels: list[str],
    threshold: float,
) -> dict[str, float]:
    """Меряет метрики уже сохранённого артефакта."""

    router = LinearIntentRouter.load(path)

    if router is None:
        return {
            "top1": 0.0,
            "macro_f1": 0.0,
            "correct": 0.0,
            "ci": 0.0,
            "coverage": 0.0,
            "selective": 0.0,
        }

    predictions = []
    confidences = []

    for text in texts:
        result = router.predict(text)

        if result is None:
            predictions.append("")
            confidences.append(0.0)
            continue

        predicted, confidence = result
        predictions.append(predicted)
        confidences.append(confidence)

    correct = sum(
        1
        for expected, predicted in zip(
            labels,
            predictions,
            strict=False,
        )
        if expected == predicted
    )
    per_class = class_metrics(labels, predictions)
    interval = bootstrap_metrics(
        labels,
        predictions,
        iterations=300,
    )
    covered = [
        (expected, predicted)
        for expected, predicted, confidence in zip(
            labels,
            predictions,
            confidences,
            strict=False,
        )
        if confidence >= threshold
    ]
    coverage = len(covered) / len(labels) if labels else 0.0
    selective = (
        sum(
            1
            for expected, predicted in covered
            if expected == predicted
        )
        / len(covered)
        if covered
        else 0.0
    )
    ece, brier = calibration_metrics(
        confidences,
        [
            expected == predicted
            for expected, predicted in zip(
                labels,
                predictions,
                strict=False,
            )
        ],
    )

    return {
        "top1": correct / len(labels) if labels else 0.0,
        "macro_f1": macro_f1(per_class),
        "correct": float(correct),
        "ci": (interval["top1_high"] - interval["top1_low"]) / 2,
        "coverage": coverage,
        "selective": selective,
        "ece": ece,
        "brier": brier,
    }


def update_meta(path: Path, updates: dict) -> None:
    """Дописывает поля в meta готового артефакта."""

    document = json.loads(path.read_text(encoding="utf-8"))
    document["meta"].update(updates)
    path.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


def coefficient_rows(
    model: LogisticRegression,
) -> tuple[list[np.ndarray], list[float]]:
    """Приводит бинарную модель к двум строкам весов."""

    if len(model.classes_) == 2 and model.coef_.shape[0] == 1:
        zeros = np.zeros_like(model.coef_[0])

        return (
            [zeros, model.coef_[0]],
            [0.0, float(model.intercept_[0])],
        )

    return (
        [row for row in model.coef_],
        [float(value) for value in model.intercept_],
    )


def compact_weights(
    model: LogisticRegression,
    limit: int,
) -> list[list[list[float]]]:
    """Оставляет самые весомые признаки каждого класса."""

    rows, _intercept = coefficient_rows(model)
    weights = []

    for row in rows:
        nonzero = np.flatnonzero(row)

        if limit > 0 and len(nonzero) > limit:
            order = np.argsort(np.abs(row[nonzero]))
            nonzero = nonzero[order[-limit:]]

        weights.append(
            [
                [int(index), round(float(row[index]), 6)]
                for index in nonzero
            ]
        )

    return weights


def export_router(
    vectorizer: TfidfVectorizer,
    model: LogisticRegression,
    output: Path,
    top_weights: int,
    meta: dict,
    temperature: float,
) -> None:
    """Пишет компактный JSON, пригодный для чистого Python."""

    pairs = sorted(
        vectorizer.vocabulary_.items(),
        key=lambda item: item[1],
    )
    _rows, intercept = coefficient_rows(model)
    document = {
        "meta": {
            "version": 1,
            "created": date.today().isoformat(),
            "classes": len(model.classes_),
            "ngram_range": list(NGRAM_RANGE),
            "top_weights": top_weights,
            "temperature": round(temperature, 4),
            **meta,
        },
        "labels": [str(label) for label in model.classes_],
        "vocabulary": [gram for gram, _index in pairs],
        "idf": [
            round(float(vectorizer.idf_[index]), 6)
            for _gram, index in pairs
        ],
        "intercept": [
            round(float(value), 6)
            for value in intercept
        ],
        "weights": compact_weights(model, top_weights),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
