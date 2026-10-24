# Giperion/tools/check_control_questions.py                    v001
# Проверка распознавания на фиксированных контрольных вопросах.
# Последнее изменение: добавлены проверка совпадений и учёт неизвестных запросов.

import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.text_tools import normalize_message
from train_intent_model import load_training_examples


CONTROL_QUESTIONS: tuple[tuple[str, str | None], ...] = (
    ("что мы уже сделали в проекте", "project"),
    ("хочу разобраться с функциями в питоне", "python"),
    ("посоветуй книгу на вечер", "books"),
    ("есть ли прогноз дождя", "weather"),
    ("расскажи о жизни животных", "animals"),
    ("как тебя представить другу", "bot_identity"),
    ("я расстроен и хочу поговорить", "emotions_negative"),
    ("что посмотреть сегодня вечером", "movies"),
    ("сломан холодильник, вода на полу", None),
    ("абракадабра неизвестная тема", None),
)

THRESHOLDS = (0.50, 0.60, 0.70, 0.80)


def check_no_exact_matches(
    training_phrases: list[str],
) -> None:
    """Не допускает точных копий контрольных вопросов в обучении."""

    known_phrases = set(training_phrases)
    seen_questions = set()

    for question, _ in CONTROL_QUESTIONS:
        normalized = normalize_message(question)

        if not normalized:
            raise ValueError(
                "В контрольном наборе есть пустой вопрос."
            )

        if normalized in seen_questions:
            raise ValueError(
                f"Контрольный вопрос повторяется: «{question}»."
            )

        if normalized in known_phrases:
            raise ValueError(
                "Контрольный вопрос уже есть в intents.json: "
                f"«{question}»."
            )

        seen_questions.add(normalized)


def main() -> None:
    """Проверяет фиксированные вопросы без изменения файлов."""

    training_phrases, training_categories = (
        load_training_examples()
    )

    check_no_exact_matches(training_phrases)

    questions = [
        normalize_message(question)
        for question, _ in CONTROL_QUESTIONS
    ]

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        lowercase=False,
    )

    training_vectors = vectorizer.fit_transform(
        training_phrases
    )
    question_vectors = vectorizer.transform(
        questions
    )

    similarities = cosine_similarity(
        question_vectors,
        training_vectors,
    )

    results = []

    for (question, expected), row in zip(
        CONTROL_QUESTIONS,
        similarities,
    ):
        nearest_index = int(row.argmax())

        results.append(
            {
                "question": question,
                "expected": expected,
                "predicted": training_categories[
                    nearest_index
                ],
                "nearest": training_phrases[
                    nearest_index
                ],
                "similarity": float(
                    row[nearest_index]
                ),
            }
        )

    print(
        f"Обучающих фраз: {len(training_phrases)}"
    )
    print(
        f"Контрольных вопросов: {len(results)}"
    )

    print()
    print("Результат без порога:")

    for result in results:
        expected = result["expected"] or "неизвестно"

        print(
            f"- «{result['question']}»"
            f"\n  Ожидалось: {expected}; "
            f"найдено: {result['predicted']}; "
            f"сходство: {result['similarity']:.2f}"
            f"\n  Ближайшая фраза: "
            f"«{result['nearest']}»"
        )

    print()
    print(
        "Порог | Принято известных | "
        "Верно принятых | "
        "Ошибочно принятых неизвестных"
    )

    for threshold in THRESHOLDS:
        accepted_known = [
            result
            for result in results
            if (
                result["expected"] is not None
                and result["similarity"] >= threshold
            )
        ]

        correct_known = sum(
            result["predicted"] == result["expected"]
            for result in accepted_known
        )

        accepted_unknown = sum(
            result["expected"] is None
            and result["similarity"] >= threshold
            for result in results
        )

        print(
            f"{threshold:.2f}  | "
            f"{len(accepted_known)} из 8          | "
            f"{correct_known}              | "
            f"{accepted_unknown} из 2"
        )

    print()
    print(
        "Это маленький контрольный набор, "
        "а не окончательная оценка качества. "
        "Файлы проекта не изменены."
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
