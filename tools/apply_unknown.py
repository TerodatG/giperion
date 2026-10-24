# Giperion/tools/apply_unknown.py                                 v001
# Применяет разметку непонятых фраз: вливает в intents и чистит накопитель.
# Последнее изменение: первый вариант — add/trash/skip по черновику label_unknown.

import json
from pathlib import Path

from app.language.learning_service import add_phrase_to_category
from app.memory.memory import remove_unknown_messages
from config import DATA_DIR

LABELS_FILE = DATA_DIR / "unknown_labels.json"


def main() -> None:
    """Применяет черновик разметки и печатает итог."""

    if not LABELS_FILE.exists():
        print(f"Черновик не найден: {LABELS_FILE}")
        print("Сначала запусти: python -m tools.label_unknown")

        return

    with Path(LABELS_FILE).open(
        "r",
        encoding="utf-8",
    ) as file:
        labels = json.load(file).get("labels", [])

    if not labels:
        print("Черновик пуст — нечего применять.")

        return

    added = 0
    removed_texts = []
    skipped = 0

    for record in labels:
        text = record.get("text", "")
        action = record.get("action")

        if action == "add":
            tag = record.get("tag")

            if not isinstance(tag, str) or not tag.strip():
                print(f"«{text}»: действие add без tag — пропущено, останется в накопителе.")

                skipped += 1

                continue

            message = add_phrase_to_category(
                text,
                tag,
            )

            # Дубль тоже означает: бот эту фразу понимает — убираем из накопителя.
            removed_texts.append(text)
            added += 1

            print(f"«{text}» → {tag}: {message}")

        elif action == "trash":
            removed_texts.append(text)

            print(f"«{text}» → мусор: убран из накопителя.")

        else:
            skipped += 1

    if removed_texts:
        remove_unknown_messages(removed_texts)

    print()
    print(f"Добавлено в намерения: {added}")
    print(f"Убрано из накопителя: {len(removed_texts)}")
    print(f"Оставлено (skip и ошибки): {skipped}")

    if added:
        print()
        print("Дальше — переобучение:")
        print("python -m training.build_dataset")
        print("python -m training.tokenizer")
        print("python -m training.char_tokenizer")
        print("python -m training.train_charcnn --full")
        print("python -m training.train_seq2seq")


if __name__ == "__main__":
    main()
