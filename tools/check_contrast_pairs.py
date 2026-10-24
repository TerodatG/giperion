# Giperion/tools/check_contrast_pairs.py                       v007
# Проверка близких новых фраз с разными ожидаемыми категориями.
# Последнее изменение: исправлена ожидаемая категория joke в шестой контрастной паре.

import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import make_pipeline

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.text_tools import normalize_message
from train_intent_model import load_training_examples


CONTRAST_PAIRS = (
    (
        ("я согласен с тобой", "agree"),
        ("я не согласен с тобой", "disagree"),
    ),
    (
        ("это хорошая идея", "agree"),
        ("это плохая идея", "disagree"),
    ),
    (
        ("машина сломалась в дороге", "transport"),
        ("ты машина или человек", "bot_identity"),
    ),
    (
        (
            "нейросеть — это современная технология",
            "technology",
        ),
        (
            "считаешь себя нейросетью",
            "bot_identity",
        ),
    ),
    (
        ("как у тебя продвигаются дела", "how_are_you"),
        ("как продвигается проект Giperion", "project"),
    ),
    (
        ("мне очень весело сегодня", "emotions_positive"),
        ("расскажи смешную историю", "joke"),
    ),
    (
        ("мне хорошо и спокойно", "emotions_positive"),
        ("хорошо, я согласен", "agree"),
    ),
    (
        ("какую еду выбрать на ужин", "food"),
        ("что можно приготовить на ужин дома", "cooking"),
    ),
)


def validate_pairs_not_in_training(
    training_phrases: list[str],
) -> None:
    """Проверяет, что контрольные фразы не входят в обучение."""

    known_phrases = {
        normalize_message(phrase)
        for phrase in training_phrases
    }
    seen_phrases = set()
    duplicates_in_training = []
    duplicates_in_pairs = []

    for pair in CONTRAST_PAIRS:
        for phrase, _ in pair:
            normalized = normalize_message(phrase)

            if not normalized:
                raise ValueError(
                    "В контрастных парах найдена пустая фраза."
                )

            if normalized in seen_phrases:
                duplicates_in_pairs.append(phrase)

            if normalized in known_phrases:
                duplicates_in_giperion.training.append(phrase)

            seen_phrases.add(normalized)

    if duplicates_in_pairs:
        phrases = ", ".join(
            f"«{phrase}»"
            for phrase in duplicates_in_pairs
        )
        raise ValueError(
            "Контрольные фразы повторяются: "
            f"{phrases}."
        )

    if duplicates_in_training:
        phrases = ", ".join(
            f"«{phrase}»"
            for phrase in duplicates_in_training
        )
        raise ValueError(
            "Контрольные фразы уже есть в intents.json: "
            f"{phrases}."
        )


def predict_by_similarity(
    train_phrases: list[str],
    train_categories: list[str],
    test_phrases: list[str],
) -> list[tuple[str, str, float]]:
    """Находит ближайшую обучающую фразу для каждого запроса."""

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

    results = []

    for row in similarities:
        nearest_index = int(row.argmax())

        results.append(
            (
                train_categories[nearest_index],
                train_phrases[nearest_index],
                float(row[nearest_index]),
            )
        )

    return results


def predict_by_classifier(
    train_phrases: list[str],
    train_categories: list[str],
    test_phrases: list[str],
) -> list[str]:
    """Обучает классификатор и предсказывает новые фразы."""

    model = make_pipeline(
        TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            lowercase=False,
        ),
        LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
        ),
    )

    model.fit(
        train_phrases,
        train_categories,
    )

    return list(
        model.predict(test_phrases)
    )


def main() -> None:
    """Проверяет контрастные фразы без изменения файлов проекта."""

    train_phrases, train_categories = (
        load_training_examples()
    )

    validate_pairs_not_in_training(train_phrases)

    similarity_correct = 0
    classifier_correct = 0
    total = 0

    print(
        f"Контрастных пар: {len(CONTRAST_PAIRS)}"
    )
    print(
        "Все проверочные фразы отсутствуют "
        "в intents.json."
    )

    for pair_number, pair in enumerate(
        CONTRAST_PAIRS,
        start=1,
    ):
        test_phrases = [
            normalize_message(phrase)
            for phrase, _ in pair
        ]

        similarity_results = predict_by_similarity(
            train_phrases,
            train_categories,
            test_phrases,
        )

        classifier_results = predict_by_classifier(
            train_phrases,
            train_categories,
            test_phrases,
        )

        print()
        print(f"Пара {pair_number}:")

        for index, (phrase, expected) in enumerate(pair):
            (
                similarity_category,
                nearest_phrase,
                similarity,
            ) = similarity_results[index]

            classifier_category = classifier_results[index]

            similarity_is_correct = (
                similarity_category == expected
            )
            classifier_is_correct = (
                classifier_category == expected
            )

            similarity_correct += similarity_is_correct
            classifier_correct += classifier_is_correct
            total += 1

            similarity_mark = (
                "верно"
                if similarity_is_correct
                else "ошибка"
            )
            classifier_mark = (
                "верно"
                if classifier_is_correct
                else "ошибка"
            )

            print(
                f"- «{phrase}» → "
                f"ожидалось {expected}"
            )
            print(
                "  Похожая фраза: "
                f"{similarity_category} "
                f"({similarity_mark}, "
                f"сходство {similarity:.2f}); "
                f"«{nearest_phrase}»"
            )
            print(
                "  Классификатор: "
                f"{classifier_category} "
                f"({classifier_mark})"
            )

    print()
    print(
        "Поиск похожей фразы: "
        f"{similarity_correct} из {total}"
    )
    print(
        "Классификатор: "
        f"{classifier_correct} из {total}"
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
