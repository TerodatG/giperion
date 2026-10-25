# Giperion/tools/label_unknown.py                                 v002
# Черновик разметки непонятых фраз с подсказкой нейросети.
# Последнее изменение: черновик пишется через общий атомарный слой.

from config import DATA_DIR
from giperion.language.intent_handler import load_intents
from giperion.neural_engine import CONFIDENCE_THRESHOLD, _build_engine
from shared.storage.json_store import write_json
from shared.text_tools import normalize_message
from terminal.memory.memory import get_unknown_messages

LABELS_FILE = DATA_DIR / "unknown_labels.json"


def build_pattern_index() -> dict[str, str]:
    """Собирает соответствие: нормализованная фраза → тег намерения."""

    index = {}

    for intent in load_intents():
        tag = intent.get("tag")

        if not isinstance(tag, str):
            continue

        for pattern in intent.get("patterns", []):
            index[normalize_message(pattern)] = tag

    return index


def suggest_action(
    text: str,
    pattern_index: dict[str, str],
    engine,
) -> tuple[str, str | None, str]:
    """Предлагает действие для одной фразы: add, trash или skip."""

    exact_tag = pattern_index.get(
        normalize_message(text)
    )

    if exact_tag:
        return (
            "trash",
            None,
            f"уже есть в «{exact_tag}» — убрать из накопителя",
        )

    if engine is None:
        return (
            "skip",
            None,
            "нейросеть недоступна — разметь вручную",
        )

    label, confidence = engine.classify(text)

    if confidence >= CONFIDENCE_THRESHOLD:
        return (
            "add",
            label,
            f"предложено моделью: {label} ({confidence:.2f})",
        )

    return (
        "skip",
        None,
        f"модель не уверена: {label} ({confidence:.2f}) — "
        "впиши тег вручную или пометь мусор",
    )


def main() -> None:
    """Печатает разбор накопителя и пишет черновик разметки."""

    unknown_messages = get_unknown_messages()

    if not unknown_messages:
        print("Непонятых фраз нет — цикл разметки не нужен.")

        return

    pattern_index = build_pattern_index()
    engine = _build_engine()

    labels = []

    print(f"--- Разбор накопителя: {len(unknown_messages)} ---")
    print()

    for message in unknown_messages:
        text = message.get("text", "")

        if not isinstance(text, str) or not text.strip():
            continue

        action, tag, note = suggest_action(
            text,
            pattern_index,
            engine,
        )

        record = {
            "text": text,
            "action": action,
            "note": note,
        }

        if tag:
            record["tag"] = tag

        labels.append(record)

        tag_line = f" → {tag}" if tag else ""
        print(f"«{text}»{tag_line}")
        print(f"    {action}: {note}")
        print()

    write_json(
        LABELS_FILE,
        {
            "_meta": {
                "path": "Giperion/data/unknown_labels.json",
                "description": (
                    "Черновик разметки непонятых фраз. "
                    "add — добавить в intents (указать tag) и убрать "
                    "из накопителя; trash — мусор, убрать из накопителя; "
                    "skip — оставить как есть. Проверь черновик и запусти "
                    "python -m tools.apply_unknown"
                ),
                "actions": {
                    "add": "в intents.json (нужен tag) + убрать из накопителя",
                    "trash": "убрать из накопителя, в намерения не добавлять",
                    "skip": "оставить в накопителе",
                },
            },
            "labels": labels,
        },
    )

    print(f"Черновик сохранён: {LABELS_FILE}")
    print("Проверь его, поправь action/tag при необходимости и запусти:")
    print("python -m tools.apply_unknown")


if __name__ == "__main__":
    main()
