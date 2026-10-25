# Giperion/app/core/model_catalog.py                              v006
# Каталог моделей: чтение, проверка полей и поиск по идентификатору.
# Последнее изменение: короткий ник модели для чата.

from terminal.core import model_files
from terminal.core.model_availability import is_model_unavailable
from shared.storage.json_store import read_json_object

# Модель по умолчанию — собственное ядро проекта.
DEFAULT_MODEL_ID = "giperion"

# Псевдогруппа для закладки «Компаньоны»: модели, отмеченные в карточке.
COMPANION_GROUP = "companions"

# Псевдогруппа для закладки «Сенат»: участники общего диалога.
CONFERENCE_GROUP = "conference"

# Группы-закладки окна «Модель»: ключ в данных и подпись.
MODEL_GROUPS = (
    (CONFERENCE_GROUP, "Сенат"),
    (COMPANION_GROUP, "Компаньоны"),
    ("popular", "Популярные"),
    ("other", "Другие"),
    ("own", "Свои"),
)

# Сильные стороны, которые показывает карточка модели.
DEFAULT_STRENGTHS = (
    "Текст",
    "Графика",
    "Видео",
    "Кодинг",
    "Творчество",
)


def _clean_capabilities(value: object) -> dict:
    """Проверяет описание функций модели для карточки."""

    if not isinstance(value, dict):
        return {}

    modalities = value.get("modalities")
    limits = value.get("limit")

    clean_modalities = {"input": [], "output": []}

    if isinstance(modalities, dict):
        for direction in ("input", "output"):
            values = modalities.get(direction)

            if isinstance(values, list):
                clean_modalities[direction] = [
                    str(item)
                    for item in values
                    if isinstance(item, str)
                ]

    clean_limits = {"context": 0, "output": 0}

    if isinstance(limits, dict):
        for key in ("context", "output"):
            try:
                clean_limits[key] = max(0, int(limits.get(key, 0)))
            except (TypeError, ValueError):
                clean_limits[key] = 0

    return {
        "attachment": bool(value.get("attachment", False)),
        "reasoning": bool(value.get("reasoning", False)),
        "tool_call": bool(value.get("tool_call", False)),
        "structured_output": bool(
            value.get("structured_output", False)
        ),
        "temperature": bool(value.get("temperature", False)),
        "modalities": clean_modalities,
        "limit": clean_limits,
        "status": str(value.get("status", "active")),
    }


def _clean_nickname(value: object, name: str) -> str:
    """Короткий ник модели: без версии и уточнений в скобках."""

    if isinstance(value, str):
        nickname = value.strip()

        if nickname:
            return nickname[:60]

    fallback = name.strip()
    fallback = fallback.split(" (", 1)[0]
    fallback = fallback.replace(" Free", "")

    return fallback[:60] or name[:60]


def _parse_model(record: dict) -> dict | None:
    """Превращает запись каталога в модель с проверенными полями."""

    if not isinstance(record, dict):
        return None

    model_id = record.get("id")
    name = record.get("name")

    if not isinstance(model_id, str) or not isinstance(name, str):
        return None

    avatar = record.get("avatar")
    parameters = record.get("parameters")
    strengths = record.get("strengths")

    clean_strengths = {}

    if isinstance(strengths, dict):
        for key, value in strengths.items():
            if not isinstance(key, str):
                continue

            try:
                clean_strengths[key] = max(0, min(5, int(value)))
            except (TypeError, ValueError):
                continue

    try:
        context_limit = max(0, int(record.get("context_limit", 0)))
    except (TypeError, ValueError):
        context_limit = 0

    try:
        token_budget = max(0, int(record.get("token_budget", 0)))
    except (TypeError, ValueError):
        token_budget = 0

    return {
        "id": model_id,
        "name": name,
        "nickname": _clean_nickname(
            record.get("nickname"),
            name,
        ),
        "provider": str(record.get("provider", "")),
        "description": str(record.get("description", "")),
        "available": bool(record.get("available", False)),
        "group": str(record.get("group", "other")),
        "avatar": avatar if isinstance(avatar, str) else "",
        "url": str(record.get("url", "")),
        "api": str(record.get("api", "")),
        "price": str(record.get("price", "")),
        "model_id": str(record.get("model_id", "")),
        "provider_id": str(record.get("provider_id", "")),
        "context_limit": context_limit,
        "token_budget": token_budget,
        "strengths": clean_strengths,
        "capabilities": _clean_capabilities(
            record.get("capabilities")
        ),
        "parameters": (
            parameters if isinstance(parameters, dict) else {}
        ),
    }


def load_models() -> list[dict]:
    """Читает каталог и свои модели.

    Первой в списке всегда идёт модель по умолчанию, даже если
    в файле она записана не первой.
    """

    models = []

    for path in (
        model_files.MODELS_FILE,
        model_files.CUSTOM_MODELS_FILE,
    ):
        document = read_json_object(path)

        for record in document.get("models", []):
            model = _parse_model(record)

            if model is None:
                continue

            # Недоступные и нерабочие модели не показываем.
            if is_model_unavailable(model):
                continue

            models.append(model)

    models.sort(
        key=lambda model: model["id"] != DEFAULT_MODEL_ID
    )

    return models


def get_model(model_id: str) -> dict | None:
    """Возвращает модель по идентификатору или None."""

    for model in load_models():
        if model["id"] == model_id:
            return model

    return None
