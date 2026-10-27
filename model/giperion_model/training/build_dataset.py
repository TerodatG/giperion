# GiperionModel/giperion_model/training/build_dataset.py              v003
# Сбор обучающего датасета из намерений и истории диалогов.
# Последнее изменение: общий слой чтения и записи JSON.

from giperion_model._shared.json_store import read_json, write_json
from giperion_model.config import (
    CONVERSATIONS_FILE,
    DATA_DIR,
    UNKNOWN_MESSAGES_FILE,
)

INTENTS_FILE = DATA_DIR / "intents.json"

DATASET_DIR = DATA_DIR / "dataset"
CLASSIFICATION_FILE = DATASET_DIR / "classification.json"
PAIRS_FILE = DATASET_DIR / "pairs.json"
UNLABELED_FILE = DATASET_DIR / "unlabeled.json"

# Собственное ядро: только его ответы считаются речью Гипериона.
GIPERION_MODEL_ID = "giperion"

# Ответы-заглушки не годятся как цель для генеративной модели.
FALLBACK_RESPONSES = (
    "Я пока не знаю, как на это ответить",
    "Я пока не понял",
    "Возможно, ты имел в виду",
)

# Служебные строки в истории: запуск скрипта и системные команды.
SKIP_USER_PREFIXES = (
    "c:\\",
    "[система]",
    "гиперион, система",
)
SKIP_USER_SUBSTRINGS = (
    "python3.13.exe",
)

# Служебные команды, попавшие в список непонятых фраз.
SERVICE_UNKNOWN_PREFIXES = (
    "создай категорию",
    "научи фразе",
    "удали",
    "измени ответ",
    "покажи категории",
    "покажи фразы",
    "покажи файлы",
    "покажи архивы",
    "покажи непонятные",
    "очисти",
    "архив",
    "отмена",
    "подтверждаю",
    "принять",
    "гиперион, система",
)


def load_intents() -> list[dict]:
    """Загружает намерения из списка или объекта с ключом intents."""

    document = read_json(INTENTS_FILE, [])

    if isinstance(document, dict):
        document = document.get("intents", [])

    if not isinstance(document, list):
        return []

    return [
        intent
        for intent in document
        if isinstance(intent, dict)
    ]


def is_usable_user_text(text: str) -> bool:
    """Проверяет, что фраза пользователя пригодна для обучения."""

    stripped = text.strip()

    if not stripped:
        return False

    lowered = stripped.lower()

    if any(
        lowered.startswith(prefix)
        for prefix in SKIP_USER_PREFIXES
    ):
        return False

    if any(
        substring in lowered
        for substring in SKIP_USER_SUBSTRINGS
    ):
        return False

    return True


def is_usable_response(text: str) -> bool:
    """Проверяет, что ответ не является заглушкой."""

    stripped = text.strip()

    if not stripped:
        return False

    return not any(
        stripped.startswith(prefix)
        for prefix in FALLBACK_RESPONSES
    )


def build_classification(intents: list[dict]) -> tuple[int, int]:
    """Собирает примеры «фраза → намерение». Возвращает примеры и классы."""

    examples = []
    labels = set()

    for intent in intents:
        label = intent.get("tag")
        patterns = intent.get("patterns", [])

        if not isinstance(label, str):
            continue

        if not isinstance(patterns, list):
            continue

        labels.add(label)

        for pattern in patterns:
            if not isinstance(pattern, str):
                continue

            stripped = pattern.strip()

            if not stripped:
                continue

            examples.append(
                {
                    "text": stripped,
                    "label": label,
                }
            )

    write_json(CLASSIFICATION_FILE, examples)

    return len(examples), len(labels)


def build_intent_pairs(
    intents: list[dict],
    pairs: dict[tuple, dict],
) -> int:
    """Добавляет пары «фраза → ответ» из намерений. Возвращает число."""

    added = 0

    for intent in intents:
        patterns = intent.get("patterns", [])
        responses = intent.get("responses", [])

        if not isinstance(patterns, list):
            continue

        if not isinstance(responses, list):
            continue

        for pattern in patterns:
            if not isinstance(pattern, str):
                continue

            input_text = pattern.strip()

            if not input_text:
                continue

            for response in responses:
                if not isinstance(response, str):
                    continue

                output_text = response.strip()

                if not output_text:
                    continue

                key = (input_text, output_text)

                if key not in pairs:
                    pairs[key] = {
                        "input": input_text,
                        "output": output_text,
                    }
                    added += 1

    return added


def build_conversation_pairs(
    pairs: dict[tuple, dict],
) -> tuple[int, int]:
    """Добавляет пары из истории диалогов. Возвращает добавлено и пропущено."""

    messages = read_json(CONVERSATIONS_FILE, [])

    if not isinstance(messages, list):
        return 0, 0

    added = 0
    skipped = 0
    pending_user: str | None = None

    for message in messages:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        text = str(message.get("text", "")).strip()

        if role == "user":
            if is_usable_user_text(text):
                pending_user = text
            else:
                pending_user = None

            continue

        if role == "assistant" and pending_user is not None:
            author = message.get("model")

            # Ответы внешних моделей — не речь Гипериона: не учимся на них.
            if isinstance(author, str) and author != GIPERION_MODEL_ID:
                skipped += 1
                pending_user = None

                continue

            if is_usable_response(text):
                key = (pending_user, text)

                if key not in pairs:
                    pairs[key] = {
                        "input": pending_user,
                        "output": text,
                    }
                    added += 1
            else:
                skipped += 1

            pending_user = None

    return added, skipped


def build_unlabeled() -> tuple[int, int]:
    """Собирает непонятые фразы без служебных команд. Возвращает число."""

    items = read_json(UNKNOWN_MESSAGES_FILE, [])

    if not isinstance(items, list):
        return 0, 0

    phrases = []
    skipped = 0

    for item in items:
        if not isinstance(item, dict):
            continue

        text = str(item.get("text", "")).strip()

        if not text:
            skipped += 1
            continue

        lowered = text.lower()

        if any(
            lowered.startswith(prefix)
            for prefix in SERVICE_UNKNOWN_PREFIXES
        ):
            skipped += 1
            continue

        phrases.append({"text": text})

    write_json(UNLABELED_FILE, phrases)

    return len(phrases), skipped


def main() -> None:
    """Собирает датасет и печатает статистику."""

    intents = load_intents()

    examples, classes = build_classification(intents)

    pairs: dict[tuple, dict] = {}

    # Сначала намерения, затем диалоги (без перезаписи).
    intent_pairs = build_intent_pairs(intents, pairs)

    conversation_added, conversation_skipped = (
        build_conversation_pairs(pairs)
    )

    write_json(PAIRS_FILE, list(pairs.values()))

    unlabeled, unlabeled_skipped = build_unlabeled()

    print("=== Сбор датасета Giperion ===")
    print(
        f"Классификация: {examples} примеров, "
        f"{classes} классов"
    )
    print(
        f"Пары из намерений: {intent_pairs}"
    )
    print(
        f"Пары из диалогов: {conversation_added} "
        f"(отброшено непригодных: {conversation_skipped})"
    )
    print(f"Всего пар: {len(pairs)}")
    print(
        f"Неразмеченные фразы: {unlabeled} "
        f"(отброшено служебных: {unlabeled_skipped})"
    )


if __name__ == "__main__":
    main()
