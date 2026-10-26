# Giperion/app/core/model_custom.py                               v002
# Свои модели пользователя: добавление и удаление в отдельном файле.
# Последнее изменение: удаление своей модели из каталога.

from shared.storage.json_store import update_json
from terminal.core import model_files
from terminal.core.model_catalog import (
    DEFAULT_STRENGTHS,
    _parse_model,
)


def remove_custom_model(model_id: str) -> bool:
    """Удаляет свою модель из data/custom_models.json."""

    removed = {"value": False}

    def mutate(document: dict) -> dict:
        records = document.get("models", [])

        if not isinstance(records, list):
            return document

        kept = [
            record
            for record in records
            if not (
                isinstance(record, dict)
                and record.get("id") == model_id
            )
        ]

        if len(kept) == len(records):
            return document

        document["models"] = kept
        removed["value"] = True

        return document

    update_json(
        model_files.CUSTOM_MODELS_FILE,
        mutate,
        default={},
    )

    return bool(removed["value"])


def add_custom_model(
    name: str,
    provider: str = "",
    url: str = "",
    description: str = "",
    context_limit: int = 0,
    token_budget: int = 0,
) -> dict | None:
    """Добавляет свою модель в data/custom_models.json."""

    clean_name = " ".join(name.split())

    if not clean_name:
        return None

    created: dict[str, dict | None] = {"model": None}

    def mutate(document: dict) -> dict:
        records = document.get("models", [])

        if not isinstance(records, list):
            records = []

        taken_ids = {
            record.get("id")
            for record in records
            if isinstance(record, dict)
        }

        number = len(records) + 1

        while f"custom-{number}" in taken_ids:
            number += 1

        record = {
            "id": f"custom-{number}",
            "name": clean_name,
            "provider": " ".join(provider.split()) or "своя модель",
            "description": " ".join(description.split()),
            "available": False,
            "group": "own",
            "avatar": "",
            "url": " ".join(url.split()),
            "api": "",
            "price": "",
            "model_id": "",
            "provider_id": "",
            "context_limit": max(0, int(context_limit)),
            "token_budget": max(0, int(token_budget)),
            "strengths": {
                strength: 0 for strength in DEFAULT_STRENGTHS
            },
        }

        records.append(record)
        document["models"] = records
        created["model"] = _parse_model(record)

        return document

    update_json(
        model_files.CUSTOM_MODELS_FILE,
        mutate,
        default={},
    )

    return created["model"]
