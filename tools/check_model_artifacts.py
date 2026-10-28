# Giperion/tools/check_model_artifacts.py                             v001
# Проверка согласованности роутера, eval-набора и паспорта.
# Последнее изменение: первый вариант — хеши и счётчики.

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from config import DATA_DIR, MODELS_DIR
from giperion_model.language.intent_handler import load_intents

DEFAULT_ARTIFACT = MODELS_DIR / "linear_intent.json"
DEFAULT_EVAL = DATA_DIR / "eval_set.json"
DEFAULT_PASSPORTS = DATA_DIR / "model_passports.json"
DEFAULT_CLASSIFICATION = DATA_DIR / "dataset" / "classification.json"


def sha256(path: Path) -> str:
    """Считает SHA-256 файла."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


def check_artifact(
    artifact_path: Path = DEFAULT_ARTIFACT,
    eval_path: Path = DEFAULT_EVAL,
    passports_path: Path = DEFAULT_PASSPORTS,
    classification_path: Path = DEFAULT_CLASSIFICATION,
) -> list[str]:
    """Возвращает список расхождений; пустой список — всё согласовано."""

    problems = []

    if not artifact_path.is_file():
        return [f"нет артефакта: {artifact_path}"]

    document = json.loads(artifact_path.read_text(encoding="utf-8"))
    meta = document.get("meta", {})
    labels = document.get("labels", [])

    if not isinstance(labels, list) or not labels:
        problems.append("в артефакте нет labels")
        return problems

    if int(meta.get("classes", 0)) != len(labels):
        problems.append(
            f"meta.classes={meta.get('classes')} != {len(labels)}"
        )

    tags = {
        intent["tag"]
        for intent in load_intents()
        if isinstance(intent.get("tag"), str)
    }

    if set(labels) != tags:
        problems.append("набор классов артефакта не совпадает с intents")

    phrases = json.loads(
        eval_path.read_text(encoding="utf-8")
    ).get("phrases", [])
    sources = Counter(item.get("source") for item in phrases)

    if meta.get("eval_sha256") != sha256(eval_path):
        problems.append("eval_sha256 не совпадает с eval_set.json")

    if int(meta.get("eval_size", -1)) != sources["natural"]:
        problems.append(
            f"eval_size={meta.get('eval_size')} != "
            f"{sources['natural']}"
        )

    if int(meta.get("template_size", -1)) != sources["template"]:
        problems.append(
            f"template_size={meta.get('template_size')} != "
            f"{sources['template']}"
        )

    if classification_path.is_file():
        if meta.get("dataset_sha256") != sha256(
            classification_path
        ):
            problems.append(
                "dataset_sha256 не совпадает с classification.json"
            )

    if passports_path.is_file():
        passport = json.loads(
            passports_path.read_text(encoding="utf-8")
        )["passports"]["giperion"]
        quality = passport.get("quality", {})

        if abs(
            float(quality.get("accuracy", -1))
            - float(meta.get("eval_top1", -2))
        ) > 0.0005:
            problems.append("паспорт accuracy не совпадает с артефактом")

        if int(quality.get("accuracy_total", -1)) != int(
            meta.get("eval_size", -2)
        ):
            problems.append("паспорт accuracy_total не совпадает")

    return problems


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Разбирает ключи запуска."""

    parser = argparse.ArgumentParser(
        description="Проверка согласованности артефактов модели.",
    )
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL)
    parser.add_argument(
        "--passports",
        type=Path,
        default=DEFAULT_PASSPORTS,
    )
    parser.add_argument(
        "--classification",
        type=Path,
        default=DEFAULT_CLASSIFICATION,
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Печатает расхождения и возвращает код 1, если они есть."""

    args = parse_args(argv)
    problems = check_artifact(
        args.artifact,
        args.eval,
        args.passports,
        args.classification,
    )

    if not problems:
        print("Артефакты согласованы.")

        return 0

    print("Расхождения:")

    for problem in problems:
        print(f"- {problem}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
