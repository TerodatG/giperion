# Giperion/tools/update_passport.py                                  v001
# Пересчитывает паспорт Гипериона: параметры, данные и качество.
# Последнее изменение: первый вариант — метрики на отложенном наборе.

import json
import statistics
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import torch
from giperion_model.training.char_tokenizer import (
    CHAR_TOKENIZER_FILE,
    CharTokenizer,
)
from giperion_model.training.tokenizer import (
    TOKENIZER_FILE,
    WordTokenizer,
)

from config import DATA_DIR, MODELS_DIR
from shared.storage.json_store import read_json, write_json
from terminal.core.model_passport import PASSPORTS_FILE
from terminal.core.model_registry import load_models
from tools.eval_intent_model import (
    build_model,
    classify,
    load_examples,
)

PAIRS_FILE = DATA_DIR / "dataset" / "pairs.json"
INTENTS_FILE = DATA_DIR / "intents.json"
EVAL_FILE = DATA_DIR / "eval_set.json"

MODEL_ID = "giperion"


def count_params(path: Path) -> int | None:
    """Считает параметры чекпоинта."""

    if not path.exists():
        return None

    checkpoint = torch.load(
        path,
        map_location="cpu",
        weights_only=False,
    )

    state = (
        checkpoint.get("model_state")
        if isinstance(checkpoint, dict)
        else checkpoint
    )

    if not isinstance(state, dict):
        return None

    return sum(
        tensor.numel()
        for tensor in state.values()
        if hasattr(tensor, "numel")
    )


def macro_f1(
    expected: list[str],
    predicted: list[str],
) -> float:
    """Среднее F1 по классам, которые есть в проверке."""

    tp = Counter()
    fp = Counter()
    fn = Counter()

    for true_label, guess in zip(expected, predicted, strict=False):
        if true_label == guess:
            tp[true_label] += 1
        else:
            fp[guess] += 1
            fn[true_label] += 1

    scores = []

    for label in set(expected):
        precision = (
            tp[label] / (tp[label] + fp[label])
            if tp[label] + fp[label]
            else 0.0
        )
        recall = (
            tp[label] / (tp[label] + fn[label])
            if tp[label] + fn[label]
            else 0.0
        )
        scores.append(
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )

    return sum(scores) / len(scores) if scores else 0.0


def intents_counts() -> tuple[int, int]:
    """Возвращает число намерений и фраз."""

    document = json.loads(INTENTS_FILE.read_text(encoding="utf-8"))
    intents = (
        document.get("intents", document)
        if isinstance(document, dict)
        else document
    )

    if not isinstance(intents, list):
        return 0, 0

    patterns = sum(
        len(intent.get("patterns", []))
        for intent in intents
        if isinstance(intent, dict)
    )

    return len(intents), patterns


def fill_catalog_passports(
    passports: dict,
    today: str,
) -> int:
    """Заполняет паспорта внешних моделей данными каталога."""

    filled = 0

    for model in load_models():
        if model["id"] == MODEL_ID:
            continue

        entry = passports.setdefault(model["id"], {})
        entry["updated"] = today
        entry["source"] = "каталог моделей"

        capabilities = model.get("capabilities") or {}
        limits = capabilities.get("limit") or {}
        modalities = capabilities.get("modalities") or {}
        inputs = modalities.get("input") or []

        architecture = entry.setdefault("architecture", {})
        architecture["kind"] = (
            f"{model['provider']} · "
            f"{model.get('model_id') or model['id']}"
        )
        architecture["context_tokens"] = (
            model.get("context_limit") or None
        )
        architecture["output_tokens"] = limits.get("output") or None
        architecture["input"] = list(inputs)
        architecture["output"] = list(
            modalities.get("output") or []
        )

        access = entry.setdefault("access", {})
        access["provider"] = model["provider"]
        access["api"] = model["api"]
        access["price"] = model["price"]
        access["status"] = (
            "доступна"
            if model["available"]
            else "канал не настроен"
        )

        if model.get("url"):
            access["url"] = model["url"]

        features = entry.setdefault("features", {})
        features["reasoning"] = bool(capabilities.get("reasoning"))
        features["tools"] = bool(capabilities.get("tool_call"))
        features["structured"] = bool(
            capabilities.get("structured_output")
        )
        features["vision"] = "image" in inputs
        features["pdf"] = "pdf" in inputs
        features["video"] = "video" in inputs
        features["audio"] = "audio" in inputs
        features["temperature"] = bool(
            capabilities.get("temperature")
        )

        notes = entry.setdefault("notes", [])

        if not notes:
            notes.append(
                "Паспорт заполнен из каталога моделей: "
                "качество на нашем наборе не измерялось."
            )

        filled += 1

    return filled


def main() -> None:
    """Обновляет паспорт и печатает сводку."""

    model, labels, max_len = build_model()
    word_tokenizer = WordTokenizer.load(TOKENIZER_FILE)
    char_tokenizer = CharTokenizer.load(CHAR_TOKENIZER_FILE)

    examples, _ = load_examples(set(labels))

    expected = [example["label"] for example in examples]
    predicted = []
    confidences = []

    for example in examples:
        guess, confidence = classify(
            model,
            labels,
            max_len,
            example["text"],
            word_tokenizer,
            char_tokenizer,
        )
        predicted.append(guess)
        confidences.append(confidence)

    correct = sum(
        1
        for true_label, guess in zip(expected, predicted, strict=False)
        if true_label == guess
    )
    accuracy = correct / len(examples) if examples else 0.0

    document = read_json(PASSPORTS_FILE, {})

    if not isinstance(document, dict):
        document = {}

    passports = document.setdefault("passports", {})
    passport = passports.setdefault(MODEL_ID, {})

    intents, patterns = intents_counts()

    pairs = None

    if PAIRS_FILE.exists():
        try:
            pairs = len(
                json.loads(PAIRS_FILE.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError):
            pairs = None

    eval_total = len(
        json.loads(EVAL_FILE.read_text(encoding="utf-8")).get(
            "phrases",
            [],
        )
    )

    classifier_file = MODELS_DIR / "hybrid.pt"
    generator_file = MODELS_DIR / "seq2seq.pt"

    architecture = passport.setdefault("architecture", {})
    architecture["classifier_params"] = count_params(classifier_file)
    architecture["generator_params"] = count_params(generator_file)
    architecture["size_mb"] = round(
        sum(
            path.stat().st_size
            for path in (classifier_file, generator_file)
            if path.exists()
        )
        / 1024
        / 1024,
        1,
    )
    architecture["vocab_words"] = word_tokenizer.vocab_size
    architecture["vocab_chars"] = char_tokenizer.vocab_size
    architecture["context_tokens"] = max_len
    architecture["classes"] = len(labels)

    training = passport.setdefault("training", {})
    training["intents"] = intents
    training["patterns"] = patterns

    if pairs is not None:
        training["pairs"] = pairs

    training["eval_phrases"] = eval_total
    training["eval_usable"] = len(examples)

    quality = passport.setdefault("quality", {})
    quality["accuracy"] = round(accuracy, 3)
    quality["accuracy_correct"] = correct
    quality["accuracy_total"] = len(examples)
    quality["macro_f1"] = round(macro_f1(expected, predicted), 3)
    quality["mean_confidence"] = (
        round(statistics.mean(confidences), 3)
        if confidences
        else None
    )

    today = date.today().isoformat()
    passport["updated"] = today
    document.setdefault("_meta", {})["updated"] = today

    filled = fill_catalog_passports(passports, today)

    write_json(PASSPORTS_FILE, document)

    print("=== Паспорт обновлён ===")
    print(f"Точность: {accuracy:.3f} ({correct} из {len(examples)})")
    print(f"Macro-F1: {quality['macro_f1']}")
    print(f"Параметры: {architecture['classifier_params']} + "
          f"{architecture['generator_params']}")
    print(f"Паспорта внешних моделей: {filled}")
    print(f"Файл: {PASSPORTS_FILE}")


if __name__ == "__main__":
    sys.exit(main())
