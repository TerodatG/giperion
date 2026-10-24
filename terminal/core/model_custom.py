# Giperion/app/core/model_custom.py                               v001
# Свои модели пользователя: добавление в отдельный файл каталога.
# Последнее изменение: выделено из model_registry.

from terminal.core import model_files
from terminal.core.model_catalog import (
    DEFAULT_STRENGTHS,
    _parse_model,
)
from shared.storage.json_store import read_json_object, write_json


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

    document = read_json_object(model_files.CUSTOM_MODELS_FILE)
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
    write_json(model_files.CUSTOM_MODELS_FILE, document)

    return _parse_model(record)
