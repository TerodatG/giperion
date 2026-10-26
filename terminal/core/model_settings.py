# Giperion/app/core/model_settings.py                              v006
# Активная модель, компаньоны, сенат и группировка каталога.
# Последнее изменение: своя модель без канала считается недоступной.

from dataclasses import dataclass

from shared.storage.json_store import (
    read_json_object,
    update_json,
)
from terminal.core import model_files
from terminal.core.model_catalog import (
    COMPANION_GROUP,
    CONFERENCE_GROUP,
    DEFAULT_MODEL_ID,
    get_model,
    load_models,
)

# Группы моделей, которые включаются и выключаются в окне «Модель».
MODEL_GROUP_FLAGS = ("free", "go")

GROUP_LABELS = {
    "free": "Бесплатные модели",
    "go": "Модели Go",
}


def model_group_key(model: dict) -> str:
    """Группа включения модели: free, go или core (ядро и свои)."""

    api = str(model.get("api") or "")

    if api == "opencode-go":
        return "go"

    if api == "opencode":
        return "free"

    return "core"


def _flags_from_document(document: dict) -> dict[str, bool]:
    """Достаёт разрешения групп из уже прочитанных настроек."""

    raw = document.get("model_groups")
    flags = {key: True for key in MODEL_GROUP_FLAGS}

    if isinstance(raw, dict):
        for key in MODEL_GROUP_FLAGS:
            if isinstance(raw.get(key), bool):
                flags[key] = raw[key]

    return flags


def load_model_group_flags() -> dict[str, bool]:
    """Какие группы моделей сейчас разрешены."""

    return _flags_from_document(
        read_json_object(model_files.SETTINGS_FILE)
    )


def save_model_group_flags(flags: dict) -> dict[str, bool]:
    """Сохраняет разрешения групп моделей."""

    clean = {
        key: bool(flags.get(key, True))
        for key in MODEL_GROUP_FLAGS
    }

    def mutate(document: dict) -> dict:
        document["model_groups"] = clean

        return document

    update_json(
        model_files.SETTINGS_FILE,
        mutate,
        default={},
    )

    return clean


def set_model_group_enabled(group: str, enabled: bool) -> bool:
    """Включает или выключает группу моделей."""

    if group not in MODEL_GROUP_FLAGS:
        return False

    flags = load_model_group_flags()
    flags[group] = bool(enabled)
    save_model_group_flags(flags)

    return True


def is_model_enabled(
    model: dict | None,
    flags: dict[str, bool] | None = None,
) -> bool:
    """Разрешена ли группа модели (без проверки канала)."""

    return ModelPolicy(flags).enabled(model)


def model_has_channel(model: dict | None) -> bool:
    """Есть ли у модели рабочий канал: ядро или подключённый API."""

    return ModelPolicy().has_channel(model)


def is_model_usable(
    model: dict | None,
    flags: dict[str, bool] | None = None,
) -> bool:
    """Можно ли пользоваться моделью.

    Внешние модели работают через OpenCode даже без подключённого ключа —
    вместо ответа приходит заглушка, поэтому их разрешаем. Своя модель
    без канала (`api: ""`) бесполезна, пока канал не настроен.
    """

    return ModelPolicy(flags).usable(model)


@dataclass(frozen=True)
class ModelPolicy:
    """Правила доступности без чтения файла на каждую проверку.

    Окно «Модель» загружает флаги один раз и дальше спрашивает политику;
    это убирает повторение правил в UI и лишние чтения JSON.
    """

    flags: dict[str, bool] | None = None

    def __post_init__(self) -> None:
        if self.flags is None:
            object.__setattr__(self, "flags", load_model_group_flags())

    def enabled(self, model: dict | None) -> bool:
        """Включена ли группа модели."""

        if not isinstance(model, dict):
            return False

        group = model_group_key(model)

        if group not in MODEL_GROUP_FLAGS:
            return True

        return bool((self.flags or {}).get(group, True))

    def has_channel(self, model: dict | None) -> bool:
        """Есть ли у модели настоящий канал."""

        if not isinstance(model, dict):
            return False

        return (
            bool(model.get("available"))
            or str(model.get("api") or "") == "local"
        )

    def usable(self, model: dict | None) -> bool:
        """Модель включена и у неё есть канал."""

        if not isinstance(model, dict) or not self.enabled(model):
            return False

        if model_group_key(model) != "core":
            return True

        return self.has_channel(model)


def _is_usable_with(model: dict, flags: dict[str, bool]) -> bool:
    """Проверка «включена и можно пользоваться» без чтения файла."""

    return ModelPolicy(flags).usable(model)


def _stored_ids_from_document(
    document: dict,
    key: str,
) -> list[str]:
    """Сохранённые идентификаторы из уже прочитанного документа."""

    raw = document.get(key, [])

    if not isinstance(raw, list):
        return []

    known_ids = {model["id"] for model in load_models()}
    result = []

    for model_id in raw:
        if (
            isinstance(model_id, str)
            and model_id in known_ids
            and model_id not in result
        ):
            result.append(model_id)

    return result


def _stored_ids(key: str) -> list[str]:
    """Сохранённые идентификаторы без фильтра по группам."""

    return _stored_ids_from_document(
        read_json_object(model_files.SETTINGS_FILE),
        key,
    )


def _visible_ids(key: str) -> list[str]:
    """Сохранённые идентификаторы, у которых модель работает."""

    document = read_json_object(model_files.SETTINGS_FILE)
    raw = document.get(key, [])

    if not isinstance(raw, list):
        return []

    flags = _flags_from_document(document)
    models = {model["id"]: model for model in load_models()}
    visible = []

    for model_id in raw:
        model = models.get(model_id)

        if model is None or model_id in visible:
            continue

        if not _is_usable_with(model, flags):
            continue

        visible.append(model_id)

    return visible


def _save_members(key: str, model_ids: list[str]) -> list[str]:
    """Сохраняет список участия: только известные модели, без повторов."""

    known_ids = {model["id"] for model in load_models()}
    members = []

    for model_id in model_ids:
        if (
            isinstance(model_id, str)
            and model_id in known_ids
            and model_id not in members
        ):
            members.append(model_id)

    def mutate(document: dict) -> dict:
        document[key] = members

        return document

    update_json(
        model_files.SETTINGS_FILE,
        mutate,
        default={},
    )

    return members


def _set_member(key: str, model_id: str, enabled: bool) -> bool:
    """Добавляет или убирает модель из списка участия."""

    model = get_model(model_id)

    if model is None:
        return False

    # Добавлять можно только рабочую модель; убрать — любую.
    if enabled and not is_model_usable(model):
        return False

    def mutate(document: dict) -> dict:
        # Берём сохранённый список без фильтра: выключенные группы
        # не теряются.
        members = _stored_ids_from_document(document, key)

        if enabled:
            if model_id not in members:
                members.append(model_id)
        elif model_id in members:
            members.remove(model_id)

        document[key] = members

        return document

    update_json(
        model_files.SETTINGS_FILE,
        mutate,
        default={},
    )

    return True


def _is_member(key: str, model_id: str) -> bool:
    """Есть ли модель в видимом списке участия."""

    return model_id in _visible_ids(key)


def load_companion_ids() -> list[str]:
    """Идентификаторы моделей, отмеченных компаньонами.

    Компаньонов может быть несколько: для помощи выбирается лучший
    из них по репутации и навыкам. Отметить можно любую модель
    каталога, включая Гипериона. Модели выключенных групп скрываются,
    но остаются в сохранённом списке.
    """

    return _visible_ids("companions")


def save_companion_ids(model_ids: list[str]) -> list[str]:
    """Сохраняет список компаньонов, оставляя активную модель."""

    return _save_members("companions", model_ids)


def set_companion(model_id: str, enabled: bool = True) -> bool:
    """Включает или выключает модель в списке компаньонов."""

    return _set_member("companions", model_id, enabled)


def is_companion(model_id: str) -> bool:
    """Отмечена ли модель компаньоном Гипериона."""

    return _is_member("companions", model_id)


def load_conference_ids() -> list[str]:
    """Идентификаторы участников сената.

    Модели выключенных групп скрываются из сената, но остаются
    в сохранённом списке: включишь группу — они вернутся.
    """

    return _visible_ids("conference")


def save_conference_ids(model_ids: list[str]) -> list[str]:
    """Сохраняет участников сената, не теряя выбор модели."""

    return _save_members("conference", model_ids)


def set_conference_member(
    model_id: str,
    enabled: bool = True,
) -> bool:
    """Добавляет или убирает модель из участников сената."""

    return _set_member("conference", model_id, enabled)


def is_conference_member(model_id: str) -> bool:
    """Участвует ли модель в сенате."""

    return _is_member("conference", model_id)


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

    Если память о выборе пуста, испорчена или группа модели выключена,
    возвращается Гиперион.
    """

    document = read_json_object(model_files.SETTINGS_FILE)
    model_id = document.get("model_id")

    if not isinstance(model_id, str):
        return DEFAULT_MODEL_ID

    model = get_model(model_id)

    if model is None:
        return DEFAULT_MODEL_ID

    if not _is_usable_with(model, _flags_from_document(document)):
        return DEFAULT_MODEL_ID

    return model_id


def get_active_model() -> dict | None:
    """Модель, которая сейчас отвечает в чате."""

    return get_model(get_current_model_id())


def set_current_model_id(model_id: str) -> bool:
    """Запоминает активную модель.

    Активировать можно любую включённую модель каталога: у внешних пока
    нет канала связи, но выбор уже запоминается. Модель выключенной
    группы и неизвестная модель — False.
    """

    model = get_model(model_id)

    if model is None:
        return False

    allowed = {"value": True}

    def mutate(document: dict) -> dict:
        if not _is_usable_with(
            model,
            _flags_from_document(document),
        ):
            allowed["value"] = False

            return document

        document["model_id"] = model_id
        document.setdefault("companions", [])

        return document

    update_json(
        model_files.SETTINGS_FILE,
        mutate,
        default={},
    )

    return bool(allowed["value"])
