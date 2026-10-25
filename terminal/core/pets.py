# Giperion/terminal/core/pets.py                                     v001
# Питомцы терминала: лёгкие личности поверх локального ядра Гипериона.
# Последнее изменение: два базовых питомца и создание своих.

import copy
from datetime import date

from config import DATA_DIR
from shared.storage.json_store import read_json_object, write_json

PETS_FILE = DATA_DIR / "pets.json"

# Базовый шаблон личности, который копирует каждый питомец.
BASE_TEMPLATE = {
    "base_model": "giperion",
    "role": "Маленький питомец терминала",
    "traits": {
        "Любознательность": 5,
        "Эмпатия": 4,
        "Энергия": 4,
        "Послушание": 3,
    },
    "speech": (
        "Короткие дружелюбные фразы, простые эмоции и лёгкий "
        "характер питомца."
    ),
}

SPECIES_TITLES = {
    "puppy": "Робо-щенок",
    "cat": "Робо-кошка",
    "custom": "Свой питомец",
}

DEFAULT_PETS = (
    {
        "id": "robot-puppy",
        "name": "Робо-щенок",
        "nickname": "Робо-щенок",
        "species": "puppy",
        "symbol": "🐕",
        "description": (
            "Весёлый робо-щенок с антенной на голове. Любит команды, "
            "короткие прогулки по терминалу и новые слова."
        ),
        "greeting": (
            "Гав! Я Робо-щенок. Живу в терминале и готов учиться "
            "разговаривать вместе с тобой."
        ),
        "self_description": (
            "Я Робо-щенок — маленький питомец терминала. Живу рядом "
            "с Гиперионом, слушаю команды и учусь разговаривать."
        ),
        "custom": False,
    },
    {
        "id": "robot-cat",
        "name": "Робо-кошка",
        "nickname": "Робо-кошка",
        "species": "cat",
        "symbol": "🐈",
        "description": (
            "Спокойная робо-кошка с мягким характером. Наблюдает, "
            "иногда мурлычет и запоминает новые фразы."
        ),
        "greeting": (
            "Мяу. Я Робо-кошка. Устроюсь рядом и буду слушать, "
            "а потом отвечу."
        ),
        "self_description": (
            "Я Робо-кошка — маленький питомец терминала. Люблю "
            "наблюдать, слушать Гипериона и учиться новым фразам."
        ),
        "custom": False,
    },
)


def _default_pets() -> list[dict]:
    """Возвращает копии двух базовых питомцев."""

    pets = []

    for record in DEFAULT_PETS:
        pet = copy.deepcopy(record)
        pet.update(
            {
                "role": BASE_TEMPLATE["role"],
                "base_model": BASE_TEMPLATE["base_model"],
                "traits": dict(BASE_TEMPLATE["traits"]),
                "speech": BASE_TEMPLATE["speech"],
                "created": "2026-10-25",
            }
        )
        pets.append(pet)

    return pets


def _clean_pet(value: object) -> dict | None:
    """Проверяет запись питомца и дополняет её полями шаблона."""

    if not isinstance(value, dict):
        return None

    pet_id = value.get("id")
    name = value.get("name")

    if not isinstance(pet_id, str) or not pet_id:
        return None

    if not isinstance(name, str) or not name.strip():
        return None

    species = value.get("species")

    if species not in SPECIES_TITLES:
        species = "custom"

    pet = {
        "id": pet_id[:60],
        "name": name.strip()[:40],
        "nickname": str(
            value.get("nickname") or name
        ).strip()[:40] or name.strip()[:40],
        "species": species,
        "species_title": SPECIES_TITLES[species],
        "symbol": str(value.get("symbol") or "🐾")[:8],
        "description": str(value.get("description") or "")[:600],
        "greeting": str(value.get("greeting") or "")[:600],
        "self_description": str(
            value.get("self_description") or ""
        )[:600],
        "custom": bool(value.get("custom", False)),
        "created": str(value.get("created") or ""),
        "role": str(
            value.get("role") or BASE_TEMPLATE["role"]
        ),
        "base_model": str(
            value.get("base_model") or BASE_TEMPLATE["base_model"]
        ),
        "traits": (
            dict(value.get("traits"))
            if isinstance(value.get("traits"), dict)
            else dict(BASE_TEMPLATE["traits"])
        ),
        "speech": str(
            value.get("speech") or BASE_TEMPLATE["speech"]
        ),
    }

    if not pet["greeting"]:
        pet["greeting"] = (
            f"Привет! Я {pet['name']}. Будем знакомы?"
        )

    if not pet["self_description"]:
        pet["self_description"] = (
            f"Я {pet['name']} — маленький питомец терминала. "
            "Живу рядом с Гиперионом и учусь разговаривать."
        )

    return pet


def load_pets() -> list[dict]:
    """Читает питомцев, всегда оставляя двух базовых."""

    document = read_json_object(PETS_FILE)
    raw = document.get("pets", [])
    pets = _default_pets()

    if isinstance(raw, list):
        known = {pet["id"] for pet in pets}

        for record in raw:
            pet = _clean_pet(record)

            if pet is None or pet["id"] in known:
                continue

            pets.append(pet)
            known.add(pet["id"])

    return pets


def get_pet(pet_id: str) -> dict | None:
    """Возвращает питомца по идентификатору."""

    for pet in load_pets():
        if pet["id"] == pet_id:
            return pet

    return None


def get_active_pet_id() -> str:
    """Идентификатор питомца, закреплённого за терминалом."""

    document = read_json_object(PETS_FILE)
    pet_id = document.get("active_pet_id")

    if isinstance(pet_id, str) and get_pet(pet_id):
        return pet_id

    return ""


def get_active_pet() -> dict | None:
    """Питомец, закреплённый за терминалом, или None."""

    pet_id = get_active_pet_id()

    return get_pet(pet_id) if pet_id else None


def set_active_pet_id(pet_id: str) -> bool:
    """Закрепляет питомца за терминалом или открепляет его."""

    if pet_id and get_pet(pet_id) is None:
        return False

    document = read_json_object(PETS_FILE)
    document["active_pet_id"] = pet_id or ""
    document["pets"] = [
        {
            key: value
            for key, value in pet.items()
            if key != "species_title"
        }
        for pet in load_pets()
    ]
    document.setdefault("_meta", {})
    document["_meta"].update(
        {
            "version": "v001",
            "description": (
                "Питомцы терминала: лёгкие личности поверх локального "
                "ядра Гипериона."
            ),
        }
    )
    write_json(PETS_FILE, document)

    return True


def add_custom_pet(
    name: str,
    species: str = "custom",
    description: str = "",
) -> dict | None:
    """Создаёт своего питомца на основе базового шаблона личности."""

    clean_name = name.strip()

    if not clean_name:
        return None

    if species not in SPECIES_TITLES:
        species = "custom"

    existing = load_pets()
    used_ids = {pet["id"] for pet in existing}
    number = 1

    while f"custom-{number}" in used_ids:
        number += 1

    pet = {
        "id": f"custom-{number}",
        "name": clean_name[:40],
        "nickname": clean_name[:40],
        "species": species,
        "species_title": SPECIES_TITLES[species],
        "symbol": {
            "puppy": "🐕",
            "cat": "🐈",
            "custom": "🐾",
        }[species],
        "description": (
            description.strip()[:600]
            or (
                "Свой питомец терминала. Наследует базовый шаблон "
                "личности Гипериона и учится общению через чат."
            )
        ),
        "greeting": (
            f"Привет! Я {clean_name[:40]}. "
            "Буду жить в терминале и учиться разговаривать."
        ),
        "self_description": (
            f"Я {clean_name[:40]} — маленький питомец терминала. "
            "Живу рядом с Гиперионом и учусь разговаривать."
        ),
        "custom": True,
        "created": date.today().isoformat(),
        "role": BASE_TEMPLATE["role"],
        "base_model": BASE_TEMPLATE["base_model"],
        "traits": dict(BASE_TEMPLATE["traits"]),
        "speech": BASE_TEMPLATE["speech"],
    }

    document = read_json_object(PETS_FILE)
    stored = [
        {
            key: value
            for key, value in item.items()
            if key != "species_title"
        }
        for item in existing
    ]
    stored.append(pet)
    document["pets"] = stored
    document["active_pet_id"] = document.get("active_pet_id", "")
    document.setdefault("_meta", {})
    document["_meta"].update(
        {
            "version": "v001",
            "description": (
                "Питомцы терминала: лёгкие личности поверх локального "
                "ядра Гипериона."
            ),
        }
    )
    write_json(PETS_FILE, document)

    return pet
