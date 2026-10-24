# Giperion/tools/add_candidates.py                                 v003
# Вливает проверенные кандидаты перефразировок в intents.json.
# Последнее изменение: файл кандидатов теперь обязательный аргумент.

import json
import sys
from pathlib import Path

from app.language.learning_service import add_phrase_to_category


def main() -> None:
    """Добавляет кандидаты в их категории и печатает отчёт по каждому тегу."""

    if len(sys.argv) < 2:
        print(
            "Укажи файл кандидатов: "
            "python -m tools.add_candidates data/candidates.json"
        )

        return

    candidates_file = Path(sys.argv[1])

    if not candidates_file.exists():
        print(f"Файл кандидатов не найден: {candidates_file}")

        return

    with candidates_file.open(
        "r",
        encoding="utf-8",
    ) as file:
        candidates = json.load(file).get("candidates", {})

    if not candidates:
        print("В файле кандидатов пусто — нечего добавлять.")

        return

    total_added = 0
    total_skipped = 0

    for tag, phrases in candidates.items():
        tag_added = 0
        skipped_details = []

        for phrase in phrases:
            message = add_phrase_to_category(
                phrase,
                tag,
            )

            if message.startswith("Фраза добавлена"):
                tag_added += 1
            else:
                skipped_details.append(
                    (phrase, message)
                )

        total_added += tag_added
        total_skipped += len(skipped_details)

        print(
            f"{tag}: добавлено {tag_added}, "
            f"пропущено {len(skipped_details)}"
        )

        for phrase, message in skipped_details:
            print(f"   — «{phrase}»: {message}")

    print()
    print(f"Итого добавлено: {total_added}")
    print(f"Итого пропущено (дубли и ошибки): {total_skipped}")


if __name__ == "__main__":
    main()
