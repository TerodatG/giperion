# Giperion/tools/check_intents.py                              v001
# Проверка обучающих фраз и категорий в intents.json.
# Последнее изменение: добавлены подсчёт фраз и поиск пересечений категорий.

import json
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from app.language.text_tools import normalize_message
from config import DATA_DIR


INTENTS_FILE = DATA_DIR / "intents.json"


def load_intents() -> list[dict]:
    """Читает категории, не изменяя исходный файл."""

    with INTENTS_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:
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

    if not all(
        isinstance(intent, dict)
        for intent in intents
    ):
        raise ValueError(
            "В intents.json есть категория неверного формата."
        )

    return intents


def check_intents() -> None:
    """Показывает количество фраз и пересечения категорий."""

    intents = load_intents()

    phrases_by_text: dict[
        str,
        list[tuple[str, str]],
    ] = defaultdict(list)

    total_phrases = 0

    print("Категории и количество фраз:")

    for intent in intents:
        tag = intent.get("tag")
        patterns = intent.get("patterns")

        if not isinstance(tag, str) or not tag.strip():
            raise ValueError(
                "Найдена категория без названия."
            )

        if not isinstance(patterns, list) or not all(
            isinstance(pattern, str)
            for pattern in patterns
        ):
            raise ValueError(
                f"Неверный список фраз в категории «{tag}»."
            )

        print(f"- {tag}: {len(patterns)}")

        total_phrases += len(patterns)

        for pattern in patterns:
            normalized = normalize_message(pattern)

            if not normalized:
                raise ValueError(
                    f"Пустая фраза в категории «{tag}»."
                )

            phrases_by_text[normalized].append(
                (tag, pattern)
            )

    print()
    print(f"Всего категорий: {len(intents)}")
    print(f"Всего фраз: {total_phrases}")

    overlaps = []

    for normalized, occurrences in phrases_by_text.items():
        categories = {
            tag.casefold()
            for tag, _ in occurrences
        }

        if len(categories) > 1:
            overlaps.append(
                (normalized, occurrences)
            )

    print()
    print(
        "Фразы, встречающиеся "
        "в разных категориях:"
    )

    if not overlaps:
        print("- не найдены")
        return

    for normalized, occurrences in sorted(overlaps):
        categories = ", ".join(
            sorted(
                {
                    tag
                    for tag, _ in occurrences
                },
                key=str.casefold,
            )
        )

        print(
            f"- «{normalized}»: {categories}"
        )


if __name__ == "__main__":
    try:
        check_intents()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(
            f"Ошибка проверки: {error}",
            file=sys.stderr,
        )
        sys.exit(1)