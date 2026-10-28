# GiperionModel/giperion_model/language/linear_intent.py               v001
# Линейный роутер намерений: char n-grams и логистическая регрессия.
# Последнее изменение: первый вариант — веса из JSON без sklearn.

import json
import logging
import math
from collections import Counter
from pathlib import Path

from giperion_model.config import MODELS_DIR

LINEAR_MODEL_FILE = MODELS_DIR / "linear_intent.json"
NGRAM_MIN = 3
NGRAM_MAX = 5

# Порог выбран на natural-подвыборке: покрытие ~0.76 при точности ~0.95.
ROUTER_CONFIDENCE_THRESHOLD = 0.50

LOGGER = logging.getLogger(__name__)


def char_wb_ngrams(text: str) -> list[str]:
    """Повторяет char_wb-анализатор sklearn: n-граммы внутри слов."""

    ngrams = []

    for word in str(text or "").lower().split():
        padded = f" {word} "
        length = len(padded)

        for size in range(NGRAM_MIN, NGRAM_MAX + 1):
            for start in range(0, length - size + 1):
                ngrams.append(padded[start : start + size])

    return ngrams


def _features(
    text: str,
    vocabulary: dict[str, int],
    idf: list[float],
) -> dict[int, float]:
    """Строит разреженный TF-IDF вектор как у TfidfVectorizer."""

    counts = Counter(char_wb_ngrams(text))
    values = {}

    for gram, count in counts.items():
        index = vocabulary.get(gram)

        if index is None:
            continue

        values[index] = (1.0 + math.log(count)) * idf[index]

    norm = math.sqrt(sum(value * value for value in values.values()))

    if not norm:
        return {}

    return {index: value / norm for index, value in values.items()}


def _softmax(scores: list[float]) -> list[float]:
    """Переводит оценки классов в вероятности."""

    if not scores:
        return []

    best = max(scores)
    exponents = [math.exp(score - best) for score in scores]
    total = sum(exponents)

    return [value / total for value in exponents]


class LinearIntentRouter:
    """Быстрый классификатор намерений без нейросети и sklearn."""

    def __init__(
        self,
        labels: list[str],
        vocabulary: dict[str, int],
        idf: list[float],
        intercept: list[float],
        weights: list[list[tuple[int, float]]],
        threshold: float = ROUTER_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.labels = labels
        self.vocabulary = vocabulary
        self.idf = idf
        self.intercept = intercept
        self.weights = weights
        self.threshold = threshold

    @classmethod
    def load(
        cls,
        path: Path | None = None,
    ) -> "LinearIntentRouter | None":
        """Читает артефакт; при любой проблеме — None."""

        target = Path(path or LINEAR_MODEL_FILE)

        if not target.is_file():
            return None

        try:
            document = json.loads(
                target.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as error:
            LOGGER.warning(
                "Линейный роутер не загружен: %s",
                error,
            )

            return None

        try:
            router = cls(
                labels=[str(item) for item in document["labels"]],
                vocabulary={
                    str(gram): index
                    for index, gram in enumerate(
                        document["vocabulary"]
                    )
                },
                idf=[float(item) for item in document["idf"]],
                intercept=[
                    float(item) for item in document["intercept"]
                ],
                weights=[
                    [
                        (int(index), float(weight))
                        for index, weight in row
                    ]
                    for row in document["weights"]
                ],
            )
        except (KeyError, TypeError, ValueError) as error:
            LOGGER.warning(
                "Линейный роутер повреждён: %s",
                error,
            )

            return None

        if not router.is_valid():
            LOGGER.warning(
                "Линейный роутер несовместим с форматом."
            )

            return None

        return router

    def is_valid(self) -> bool:
        """Проверяет согласованность размеров артефакта."""

        classes = len(self.labels)

        return (
            classes > 0
            and len(self.idf) == len(self.vocabulary)
            and len(self.intercept) == classes
            and len(self.weights) == classes
        )

    def predict(self, text: str) -> tuple[str, float] | None:
        """Возвращает тег и вероятность лучшего класса."""

        if not str(text or "").strip():
            return None

        features = _features(text, self.vocabulary, self.idf)

        if not features:
            return None

        scores = []

        for intercept, row in zip(
            self.intercept,
            self.weights,
            strict=False,
        ):
            score = intercept

            for index, weight in row:
                value = features.get(index)

                if value is not None:
                    score += weight * value

            scores.append(score)

        probabilities = _softmax(scores)
        best = max(
            range(len(probabilities)),
            key=probabilities.__getitem__,
        )

        return self.labels[best], probabilities[best]
