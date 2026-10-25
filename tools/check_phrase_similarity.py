# Giperion/tools/check_phrase_similarity.py                    v002
# Проверка поиска похожих фраз на отложенных обучающих примерах.
# Последнее изменение: добавлена пятичастная проверка охвата и уверенных ошибок.

import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.model_selection import StratifiedKFold

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from train_intent_model import (
    RANDOM_STATE,
    load_training_examples,
)

FOLD_COUNT = 5
THRESHOLDS = (
    0.40,
    0.50,
    0.60,
    0.70,
    0.80,
    0.90,
)


def find_nearest_examples(
    train_phrases: list[str],
    train_categories: list[str],
    test_phrases: list[str],
) -> list[tuple[str, str, float]]:
    """Ищет ближайшие фразы только среди обучающих примеров."""

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        lowercase=False,
    )

    train_vectors = vectorizer.fit_transform(
        train_phrases
    )
    test_vectors = vectorizer.transform(
        test_phrases
    )

    similarities = cosine_similarity(
        test_vectors,
        train_vectors,
    )

    matches = []

    for row in similarities:
        nearest_index = int(row.argmax())

        matches.append(
            (
                train_phrases[nearest_index],
                train_categories[nearest_index],
                float(row[nearest_index]),
            )
        )

    return matches


def collect_out_of_fold_results(
    phrases: list[str],
    categories: list[str],
) -> list[dict]:
    """Проверяет каждую фразу вне её обучающей части."""

    splitter = StratifiedKFold(
        n_splits=FOLD_COUNT,
        shuffle=True,
        random_state=RANDOM_STATE,
    )

    results = []

    for fold_number, (train_indices, test_indices) in enumerate(
        splitter.split(phrases, categories),
        start=1,
    ):
        train_phrases = [
            phrases[index]
            for index in train_indices
        ]
        train_categories = [
            categories[index]
            for index in train_indices
        ]
        test_phrases = [
            phrases[index]
            for index in test_indices
        ]
        test_categories = [
            categories[index]
            for index in test_indices
        ]

        matches = find_nearest_examples(
            train_phrases,
            train_categories,
            test_phrases,
        )

        for phrase, expected, match in zip(
            test_phrases,
            test_categories,
            matches, strict=False,
        ):
            nearest_phrase, predicted, similarity = match

            results.append(
                {
                    "fold": fold_number,
                    "phrase": phrase,
                    "expected": expected,
                    "predicted": predicted,
                    "nearest": nearest_phrase,
                    "similarity": similarity,
                }
            )

        print(
            f"Часть {fold_number}: "
            f"проверено {len(test_phrases)} фраз."
        )

    return results


def show_threshold_results(
    results: list[dict],
) -> None:
    """Показывает охват и ошибки для каждого порога."""

    total = len(results)

    print()
    print(
        "Порог | Принято | Охват | "
        "Верно | Ошибок | Точность принятых"
    )

    for threshold in THRESHOLDS:
        accepted = [
            result
            for result in results
            if result["similarity"] >= threshold
        ]

        correct = sum(
            result["expected"] == result["predicted"]
            for result in accepted
        )

        errors = len(accepted) - correct
        coverage = len(accepted) / total
        precision = (
            correct / len(accepted)
            if accepted
            else 0
        )

        print(
            f"{threshold:.2f}  | "
            f"{len(accepted):4d}    | "
            f"{coverage:5.1%} | "
            f"{correct:4d}  | "
            f"{errors:4d}   | "
            f"{precision:5.1%}"
        )


def show_confident_mistakes(
    results: list[dict],
) -> None:
    """Показывает ошибки с наибольшим сходством."""

    mistakes = [
        result
        for result in results
        if result["expected"] != result["predicted"]
    ]

    mistakes.sort(
        key=lambda result: result["similarity"],
        reverse=True,
    )

    print()
    print("Ошибки с самым высоким сходством:")

    if not mistakes:
        print("- не найдены")
        return

    for result in mistakes[:15]:
        print(
            f"- «{result['phrase']}» → "
            f"{result['predicted']} "
            f"(ожидалось {result['expected']}); "
            f"ближайшая: «{result['nearest']}»; "
            f"сходство: {result['similarity']:.2f}"
        )


def main() -> None:
    """Запускает проверку, не изменяя файлы проекта."""

    phrases, categories = load_training_examples()

    print(f"Категорий: {len(set(categories))}")
    print(f"Всего фраз: {len(phrases)}")
    print(
        f"Разделений: {FOLD_COUNT}"
    )

    results = collect_out_of_fold_results(
        phrases,
        categories,
    )

    print()
    print(
        "Всего проверено отложенных фраз: "
        f"{len(results)}"
    )

    show_threshold_results(results)
    show_confident_mistakes(results)

    print()
    print(
        "Контрольные вопросы в этой проверке "
        "не использовались."
    )
    print(
        "Файлы проекта и обучающие данные "
        "не изменены."
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        print(
            f"Ошибка проверки: {error}",
            file=sys.stderr,
        )
        sys.exit(1)