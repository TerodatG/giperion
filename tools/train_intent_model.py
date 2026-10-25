# Giperion/tools/train_intent_model.py                           v003
# Сравнение и перекрёстная проверка моделей категорий Giperion.
# Последнее изменение: добавлена пятичастная проверка лучшего варианта.

import json
import sys
from collections import Counter
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import (
    StratifiedKFold,
    train_test_split,
)
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from config import DATA_DIR
from shared.text_tools import normalize_message

INTENTS_FILE = DATA_DIR / "intents.json"
TEST_SIZE = 0.25
RANDOM_STATE = 42
FOLD_COUNT = 5


def load_training_examples() -> tuple[list[str], list[str]]:
    """Читает фразы и категории без изменения файла."""

    with INTENTS_FILE.open("r", encoding="utf-8") as file:
        document = json.load(file)

    if isinstance(document, list):
        intents = document
    elif isinstance(document, dict):
        intents = document.get("intents")
    else:
        intents = None

    if not isinstance(intents, list):
        raise ValueError(
            "В intents.json не найден список категорий."
        )

    phrases = []
    categories = []
    phrase_owners = {}

    for intent in intents:
        if not isinstance(intent, dict):
            raise ValueError(
                "Обнаружена категория неверного формата."
            )

        category = intent.get("tag")
        patterns = intent.get("patterns")

        if not isinstance(category, str) or not category.strip():
            raise ValueError(
                "Обнаружена категория без названия."
            )

        if not isinstance(patterns, list):
            raise ValueError(
                f"Неверный список фраз в категории «{category}»."
            )

        for pattern in patterns:
            if not isinstance(pattern, str):
                raise ValueError(
                    f"Неверная фраза в категории «{category}»."
                )

            phrase = normalize_message(pattern)

            if not phrase:
                raise ValueError(
                    f"Пустая фраза в категории «{category}»."
                )

            previous_category = phrase_owners.get(phrase)

            if (
                previous_category is not None
                and previous_category != category
            ):
                raise ValueError(
                    f"Фраза «{phrase}» встречается "
                    f"в категориях «{previous_category}» "
                    f"и «{category}»."
                )

            phrase_owners[phrase] = category
            phrases.append(phrase)
            categories.append(category)

    counts = Counter(categories)

    if len(counts) < 2:
        raise ValueError(
            "Для обучения нужны хотя бы две категории."
        )

    if min(counts.values()) < FOLD_COUNT:
        raise ValueError(
            f"Для проверки в каждой категории нужно "
            f"не менее {FOLD_COUNT} фраз."
        )

    test_count = round(len(phrases) * TEST_SIZE)

    if test_count < len(counts):
        raise ValueError(
            "В тестовой части должно быть место "
            "для каждой категории."
        )

    return phrases, categories


def create_models() -> dict:
    """Создаёт варианты моделей для сравнения."""

    return {
        "Символы + логистическая регрессия": make_pipeline(
            TfidfVectorizer(
                analyzer="char",
                ngram_range=(2, 4),
                lowercase=False,
            ),
            LogisticRegression(max_iter=2000),
        ),
        "Символы + балансировка классов": make_pipeline(
            TfidfVectorizer(
                analyzer="char",
                ngram_range=(2, 4),
                lowercase=False,
            ),
            LogisticRegression(
                max_iter=2000,
                class_weight="balanced",
            ),
        ),
        "Символы в словах + балансировка": make_pipeline(
            TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(2, 4),
                lowercase=False,
            ),
            LogisticRegression(
                max_iter=2000,
                class_weight="balanced",
            ),
        ),
        "Слова + балансировка классов": make_pipeline(
            TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 2),
                lowercase=False,
            ),
            LogisticRegression(
                max_iter=2000,
                class_weight="balanced",
            ),
        ),
        "Символы + наивный Байес": make_pipeline(
            TfidfVectorizer(
                analyzer="char",
                ngram_range=(2, 4),
                lowercase=False,
            ),
            MultinomialNB(),
        ),
        "Символы + линейный SVM": make_pipeline(
            TfidfVectorizer(
                analyzer="char",
                ngram_range=(2, 4),
                lowercase=False,
            ),
            LinearSVC(),
        ),
    }


def count_false_greetings(
    expected: list[str],
    predicted: list[str],
) -> int:
    """Считает неверные предсказания greeting."""

    return sum(
        actual != "greeting" and guess == "greeting"
        for actual, guess in zip(expected, predicted, strict=False)
    )


def compare_models(
    phrases: list[str],
    categories: list[str],
) -> str:
    """Сравнивает модели на одном разделении."""

    (
        train_phrases,
        test_phrases,
        train_categories,
        test_categories,
    ) = train_test_split(
        phrases,
        categories,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=categories,
    )

    print(f"Фраз для обучения: {len(train_phrases)}")
    print(f"Фраз для проверки: {len(test_phrases)}")

    results = {}

    for name, model in create_models().items():
        model.fit(train_phrases, train_categories)
        predictions = list(model.predict(test_phrases))

        correct = sum(
            actual == guess
            for actual, guess in zip(
                test_categories,
                predictions, strict=False,
            )
        )
        accuracy = accuracy_score(
            test_categories,
            predictions,
        )
        macro_f1 = f1_score(
            test_categories,
            predictions,
            average="macro",
            zero_division=0,
        )
        false_greetings = count_false_greetings(
            test_categories,
            predictions,
        )

        results[name] = {
            "macro_f1": macro_f1,
            "false_greetings": false_greetings,
        }

        print()
        print(name)
        print(
            f"  Верно: {correct} из {len(test_phrases)}"
        )
        print(f"  Точность: {accuracy:.1%}")
        print(
            "  Средний F1 по категориям: "
            f"{macro_f1:.3f}"
        )
        print(
            "  Предсказаний greeting: "
            f"{predictions.count('greeting')}"
        )
        print(
            f"  Ложных greeting: {false_greetings}"
        )

    best_name = max(
        results,
        key=lambda name: (
            results[name]["macro_f1"],
            -results[name]["false_greetings"],
        ),
    )

    print()
    print(
        "Лучший результат на этом разделении: "
        f"{best_name}"
    )

    return best_name


def check_across_folds(
    phrases: list[str],
    categories: list[str],
    model_name: str,
) -> None:
    """Проверяет выбранный вариант на пяти частях данных."""

    splitter = StratifiedKFold(
        n_splits=FOLD_COUNT,
        shuffle=True,
        random_state=RANDOM_STATE,
    )

    accuracies = []
    macro_f1_scores = []
    false_greeting_counts = []

    print()
    print(
        f"Проверка «{model_name}» "
        f"на {FOLD_COUNT} разделениях:"
    )

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

        model = create_models()[model_name]
        model.fit(train_phrases, train_categories)

        predictions = list(model.predict(test_phrases))

        accuracy = accuracy_score(
            test_categories,
            predictions,
        )
        macro_f1 = f1_score(
            test_categories,
            predictions,
            average="macro",
            zero_division=0,
        )
        false_greetings = count_false_greetings(
            test_categories,
            predictions,
        )

        accuracies.append(accuracy)
        macro_f1_scores.append(macro_f1)
        false_greeting_counts.append(false_greetings)

        print(
            f"- Часть {fold_number}: "
            f"точность {accuracy:.1%}, "
            f"средний F1 {macro_f1:.3f}, "
            f"ложных greeting {false_greetings}"
        )

    print()
    print(
        "Средняя точность: "
        f"{sum(accuracies) / FOLD_COUNT:.1%}"
    )
    print(
        "Средний F1: "
        f"{sum(macro_f1_scores) / FOLD_COUNT:.3f}"
    )
    print(
        "Ложных greeting во всех частях: "
        f"{sum(false_greeting_counts)}"
    )
    print(
        "Минимальная и максимальная точность: "
        f"{min(accuracies):.1%} — "
        f"{max(accuracies):.1%}"
    )


def main() -> None:
    """Запускает сравнение и перекрёстную проверку."""

    phrases, categories = load_training_examples()

    print(f"Всего категорий: {len(set(categories))}")
    print(f"Всего фраз: {len(phrases)}")

    best_name = compare_models(phrases, categories)
    check_across_folds(
        phrases,
        categories,
        best_name,
    )

    print()
    print(
        "Файлы проекта и обучающие данные не изменены."
    )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(
            f"Ошибка обучения: {error}",
            file=sys.stderr,
        )
        sys.exit(1)
