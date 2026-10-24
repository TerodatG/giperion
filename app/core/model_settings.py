# Giperion/app/core/model_settings.py                              v004
# Активная модель, компаньоны, конференция и группировка каталога.
# Последнее изменение: участники конференции и псевдогруппа для закладки.

from app.core import model_files
from app.core.model_catalog import (
    COMPANION_GROUP,
    CONFERENCE_GROUP,
    DEFAULT_MODEL_ID,
    get_model,
    load_models,
)
from app.storage.json_store import read_json_object, write_json


def load_companion_ids() -> list[str]:
    """Идентификаторы моделей, отмеченных компаньонами Гипериона.

    Компаньонов может быть несколько: для помощи выбирается лучший
    из них по репутации и навыкам. Гиперион компаньоном быть не может.
    """

    document = read_json_object(model_files.SETTINGS_FILE)
    raw = document.get("companions", [])

    if not isinstance(raw, list):
        return []

    known_ids = {
        model["id"]
        for model in load_models()
        if model["id"] != DEFAULT_MODEL_ID
    }
    companions = []

    for model_id in raw:
        if (
            isinstance(model_id, str)
            and model_id in known_ids
            and model_id not in companions
        ):
            companions.append(model_id)

    return companions


def save_companion_ids(model_ids: list[str]) -> list[str]:
    """Сохраняет список компаньонов, оставляя активную модель.

    Возвращает очищенный список: только известные внешние модели,
    без повторов.
    """

    known_ids = {
        model["id"]
        for model in load_models()
        if model["id"] != DEFAULT_MODEL_ID
    }
    companions = []

    for model_id in model_ids:
        if (
            isinstance(model_id, str)
            and model_id in known_ids
            and model_id not in companions
        ):
            companions.append(model_id)

    document = read_json_object(model_files.SETTINGS_FILE)
    document["companions"] = companions
    write_json(model_files.SETTINGS_FILE, document)

    return companions


def set_companion(model_id: str, enabled: bool = True) -> bool:
    """Включает или выключает модель в списке компаньонов."""

    if model_id == DEFAULT_MODEL_ID or get_model(model_id) is None:
        return False

    companions = load_companion_ids()

    if enabled:
        if model_id not in companions:
            companions.append(model_id)
    elif model_id in companions:
        companions.remove(model_id)

    save_companion_ids(companions)

    return True


def is_companion(model_id: str) -> bool:
    """Отмечена ли модель компаньоном Гипериона."""

    return model_id in load_companion_ids()


def load_conference_ids() -> list[str]:
    """Идентификаторы участников конференции."""

    document = read_json_object(model_files.SETTINGS_FILE)
    raw = document.get("conference", [])

    if not isinstance(raw, list):
        return []

    known_ids = {model["id"] for model in load_models()}
    members = []

    for model_id in raw:
        if (
            isinstance(model_id, str)
            and model_id in known_ids
            and model_id not in members
        ):
            members.append(model_id)

    return members


def save_conference_ids(model_ids: list[str]) -> list[str]:
    """Сохраняет участников конференции, не теряя выбор модели."""

    known_ids = {model["id"] for model in load_models()}
    members = []

    for model_id in model_ids:
        if (
            isinstance(model_id, str)
            and model_id in known_ids
            and model_id not in members
        ):
            members.append(model_id)

    document = read_json_object(model_files.SETTINGS_FILE)
    document["conference"] = members
    write_json(model_files.SETTINGS_FILE, document)

    return members


def set_conference_member(
    model_id: str,
    enabled: bool = True,
) -> bool:
    """Добавляет или убирает модель из участников конференции."""

    if get_model(model_id) is None:
        return False

    members = load_conference_ids()

    if enabled:
        if model_id not in members:
            members.append(model_id)
    elif model_id in members:
        members.remove(model_id)

    save_conference_ids(members)

    return True


def is_conference_member(model_id: str) -> bool:
    """Участвует ли модель в конференции."""

    return model_id in load_conference_ids()


def get_models_by_group(group: str) -> list[dict]:
    """Модели одной группы-закладки."""

    if group == COMPANION_GROUP:
        companion_ids = set(load_companion_ids())

        return [
            model
            for model in load_models()
            if model["id"] in companion_ids
        ]

    if group == CONFERENCE_GROUP:
        conference_ids = set(load_conference_ids())

        return [
            model
            for model in load_models()
            if model["id"] in conference_ids
        ]

    return [
        model
        for model in load_models()
        if model["group"] == group
    ]


def get_current_model_id() -> str:
    """Идентификатор активной модели.

    Если память о выборе пуста или испорчена, возвращается Гиперион.
    """

    document = read_json_object(model_files.SETTINGS_FILE)
    model_id = document.get("model_id")

    if not isinstance(model_id, str):
        return DEFAULT_MODEL_ID

    return model_id if get_model(model_id) else DEFAULT_MODEL_ID


def get_active_model() -> dict | None:
    """Модель, которая сейчас отвечает в чате."""

    return get_model(get_current_model_id())


def set_current_model_id(model_id: str) -> bool:
    """Запоминает активную модель.

    Активировать можно любую модель из каталога: у внешних пока нет
    канала связи, но выбор уже запоминается. Неизвестная модель — False.
    """

    if get_model(model_id) is None:
        return False

    # Компаньоны живут в том же файле, поэтому не теряем их при выборе.
    document = read_json_object(model_files.SETTINGS_FILE)
    document["model_id"] = model_id
    document.setdefault("companions", [])

    write_json(model_files.SETTINGS_FILE, document)

    return True
