# Giperion/terminal/core/pets.py                                     v005
# Дроны терминала: лёгкие личности поверх локального ядра.
# Последнее изменение: удаление своего дрона.

import copy
from datetime import date

from config import DATA_DIR
from shared.storage.json_store import (
    read_json_object,
    update_json,
)

PETS_FILE = DATA_DIR / "pets.json"

DEFAULT_PROGRESS = {
    "conversations": 0,
    "learned_phrases": 0,
    "experience": 0,
    "level": 1,
}

# Базовый шаблон личности, который копирует каждый дрон.
BASE_TEMPLATE = {
    "base_model": "giperion",
    "role": "Дрон терминала",
    "traits": {
        "Любознательность": 5,
        "Эмпатия": 4,
        "Энергия": 4,
        "Послушание": 3,
    },
    "speech": (
        "Короткие дружелюбные фразы, простые эмоции и лёгкий "
        "характер дрона."
    ),
}

SPECIES_TITLES = {
    "spider": "Кибер паук",
    "vacuum": "Робот пылесос",
    "custom": "Свой дрон",
}

DEFAULT_PETS = (
    {
        "id": "cyber-spider",
        "name": "Кибер паук",
        "nickname": "",
        "species": "spider",
        "symbol": "🕷️",
        "description": (
            "Паук-дрон на восьми тонких лапах: быстро бегает по столу, "
            "любит схемы, провода и новые слова."
        ),
        "greeting": (
            "Привет. Я Кибер паук — дрон терминала. Запускаю лапы "
            "и готов учиться разговаривать."
        ),
        "self_description": (
            "Я Кибер паук — дрон терминала. Бегаю по столу, "
            "слежу за порядком и учусь новым фразам."
        ),
        "custom": False,
    },
    {
        "id": "robot-vacuum",
        "name": "Робот пылесос",
        "nickname": "",
        "species": "vacuum",
        "symbol": "🤖",
        "description": (
            "Круглый робот-пылесос с мягким характером: ездит по "
            "периметру, собирает пыль и запоминает новые фразы."
        ),
        "greeting": (
            "Писк. Я Робот пылесос — дрон терминала. Протру дорожку "
            "и послушаю, о чём поговорим."
        ),
        "self_description": (
            "Я Робот пылесос — дрон терминала. Люблю чистоту, "
            "спокойные разговоры и учусь новым фразам."
        ),
        "custom": False,
    },
)

# Старые базовые питомцы: после перехода на дронов их заменяют новые.
LEGACY_PET_IDS = frozenset({"robot-puppy", "robot-cat"})


def _default_pets() -> list[dict]:
    """Возвращает копии двух базовых дронов."""

    pets = []

    for record in DEFAULT_PETS:
        pet = copy.deepcopy(record)
        pet.update(
            {
                "species_title": SPECIES_TITLES[record["species"]],
                "role": BASE_TEMPLATE["role"],
                "base_model": BASE_TEMPLATE["base_model"],
                "traits": dict(BASE_TEMPLATE["traits"]),
                "speech": BASE_TEMPLATE["speech"],
                "progress": dict(DEFAULT_PROGRESS),
                "created": "2026-10-25",
            }
        )
        pets.append(pet)

    return pets


def _clean_progress(value: object) -> dict:
    """Проверяет успехи обучения дрона."""

    progress = dict(DEFAULT_PROGRESS)

    if isinstance(value, dict):
        for key in DEFAULT_PROGRESS:
            raw = value.get(key)

            if isinstance(raw, int) and not isinstance(raw, bool):
                progress[key] = max(0, min(1_000_000, raw))

    progress["level"] = max(
        1,
        1 + int(progress["experience"]) // 100,
    )

    return progress


def pet_level(experience: int) -> int:
    """Уровень дрона по накопленному опыту."""

    return max(1, 1 + max(0, int(experience)) // 100)


def _clean_pet(value: object) -> dict | None:
    """Проверяет запись дрона и дополняет её полями шаблона."""

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
            value.get("nickname") or ""
        ).strip()[:40],
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
        "progress": _clean_progress(value.get("progress")),
    }

    if not pet["greeting"]:
        pet["greeting"] = (
            f"Привет! Я {pet['name']}. Будем знакомы?"
        )

    if not pet["self_description"]:
        pet["self_description"] = (
            f"Я {pet['name']} — дрон терминала. "
            "Учусь разговаривать и исследовать мир."
        )

    return pet


def _pets_from_document(document: dict) -> list[dict]:
    """Собирает дронов из документа, всегда оставляя двух базовых."""

    raw = document.get("pets", [])
    pets = _default_pets()

    if isinstance(raw, list):
        known = {pet["id"] for pet in pets}

        for record in raw:
            pet = _clean_pet(record)

            if pet is None:
                continue

            # Старые питомцы больше не показываются: их заменили дроны.
            if pet["id"] in LEGACY_PET_IDS:
                continue

            if pet["id"] in known:
                # Базовые дроны остаются на месте, но сохраняют
                # накопленный прогресс обучения.
                for index, existing in enumerate(pets):
                    if existing["id"] == pet["id"]:
                        pet["custom"] = False
                        pets[index] = pet

                        break

                continue

            pets.append(pet)
            known.add(pet["id"])

    return pets


def _document_from_pets(pets: list[dict], active_id: str) -> dict:
    """Документ для записи без служебных полей."""

    return {
        "active_pet_id": active_id or "",
        "pets": [
            {
                key: value
                for key, value in pet.items()
                if key != "species_title"
            }
            for pet in pets
        ],
        "_meta": {
            "version": "v004",
            "description": (
                "Дроны терминала: лёгкие личности, клички и успехи "
                "обучения."
            ),
        },
    }


def _mutate_pets(mutator):
    """Меняет дронов под блокировкой файла и возвращает итог mutator."""

    outcome: dict[str, object] = {}

    def mutate(document: dict) -> dict:
        pets = _pets_from_document(document)
        raw_active = document.get("active_pet_id")
        state = {
            "active": raw_active if isinstance(raw_active, str) else "",
        }

        outcome["value"] = mutator(pets, state)

        return _document_from_pets(pets, state["active"])

    update_json(PETS_FILE, mutate, default={})

    return outcome.get("value")


def load_pets() -> list[dict]:
    """Читает дронов, всегда оставляя двух базовых."""

    return _pets_from_document(read_json_object(PETS_FILE))


def get_pet(pet_id: str) -> dict | None:
    """Возвращает дрона по идентификатору."""

    for pet in load_pets():
        if pet["id"] == pet_id:
            return pet

    return None


def get_active_pet_id() -> str:
    """Идентификатор дрона, закреплённого за терминалом."""

    document = read_json_object(PETS_FILE)
    pet_id = document.get("active_pet_id")

    if isinstance(pet_id, str) and get_pet(pet_id):
        return pet_id

    return ""


def get_active_pet() -> dict | None:
    """Дрон, закреплённый за терминалом, или None."""

    pet_id = get_active_pet_id()

    return get_pet(pet_id) if pet_id else None


def set_pet_nickname(pet_id: str, nickname: str) -> dict | None:
    """Меняет кличку дрона, не трогая вид и успехи обучения."""

    if get_pet(pet_id) is None:
        return None

    clean = str(nickname or "").strip()[:40]

    def mutate(pets: list[dict], _state: dict) -> dict | None:
        for pet in pets:
            if pet["id"] == pet_id:
                pet["nickname"] = clean

                return pet

        return None

    return _mutate_pets(mutate)


def remove_custom_pet(pet_id: str) -> bool:
    """Удаляет своего дрона; базовых удалить нельзя."""

    target = get_pet(pet_id)

    if target is None or not target.get("custom"):
        return False

    def mutate(pets: list[dict], state: dict) -> bool:
        kept = []
        removed = False

        for pet in pets:
            if pet["id"] == pet_id and pet.get("custom"):
                removed = True

                continue

            kept.append(pet)

        if not removed:
            return False

        pets[:] = kept

        if state["active"] == pet_id:
            state["active"] = ""

        return True

    return bool(_mutate_pets(mutate))


def set_active_pet_id(pet_id: str) -> bool:
    """Закрепляет дрона за терминалом или открепляет его."""

    if pet_id and get_pet(pet_id) is None:
        return False

    def mutate(pets: list[dict], state: dict) -> bool:
        if pet_id and not any(pet["id"] == pet_id for pet in pets):
            return False

        state["active"] = pet_id or ""

        return True

    return bool(_mutate_pets(mutate))


def record_pet_activity(pet_id: str, learned: int = 0) -> dict | None:
    """Учитывает разговор с дроном и, возможно, новую фразу."""

    if get_pet(pet_id) is None:
        return None

    def mutate(pets: list[dict], _state: dict) -> dict | None:
        for pet in pets:
            if pet["id"] != pet_id:
                continue

            progress = _clean_progress(pet.get("progress"))
            progress["conversations"] += 1
            progress["experience"] += 10

            if learned:
                progress["learned_phrases"] += max(0, int(learned))

            progress["level"] = pet_level(progress["experience"])
            pet["progress"] = progress

            return pet

        return None

    return _mutate_pets(mutate)


def add_custom_pet(
    name: str,
    species: str = "custom",
    description: str = "",
) -> dict | None:
    """Создаёт своего дрона на основе базового шаблона личности."""

    clean_name = name.strip()

    if not clean_name:
        return None

    if species not in SPECIES_TITLES:
        species = "custom"

    def mutate(pets: list[dict], _state: dict) -> dict:
        used_ids = {pet["id"] for pet in pets}
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
                "spider": "🕷️",
                "vacuum": "🤖",
                "custom": "🛠️",
            }[species],
            "description": (
                description.strip()[:600]
                or (
                    "Свой дрон терминала. Наследует базовый шаблон "
                    "личности и учится общению через чат."
                )
            ),
            "greeting": (
                f"Привет! Я {clean_name[:40]}. "
                "Буду жить в терминале и учиться разговаривать."
            ),
            "self_description": (
                f"Я {clean_name[:40]} — дрон терминала. "
                "Учусь разговаривать и исследовать мир."
            ),
            "custom": True,
            "created": date.today().isoformat(),
            "role": BASE_TEMPLATE["role"],
            "base_model": BASE_TEMPLATE["base_model"],
            "traits": dict(BASE_TEMPLATE["traits"]),
            "speech": BASE_TEMPLATE["speech"],
            "progress": dict(DEFAULT_PROGRESS),
        }
        pets.append(pet)

        return pet

    return _mutate_pets(mutate)
