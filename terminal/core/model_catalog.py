# Giperion/app/core/model_catalog.py                              v007
# Каталог моделей: чтение, проверка полей и поиск по идентификатору.
# Последнее изменение: настройки живой анимации аватара модели.

from shared.storage.json_store import read_json_object
from terminal.core import model_files
from terminal.core.model_availability import is_model_unavailable

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


def _clean_animation(value: object) -> dict:
    """Проверяет настройки живой анимации аватара модели."""

    if not isinstance(value, dict):
        return {}

    eyes = []

    for point in value.get("eyes") or []:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue

        try:
            u = float(point[0])
            v = float(point[1])
        except (TypeError, ValueError):
            continue

        eyes.append(
            (
                round(max(0.0, min(1.0, u)), 4),
                round(max(0.0, min(1.0, v)), 4),
            )
        )

    def number(key: str, default: float, low: float, high: float) -> float:
        """Читает число в разумных границах."""

        try:
            return max(low, min(high, float(value.get(key, default))))
        except (TypeError, ValueError):
            return default

    lines = value.get("lines")

    return {
        "eyes": eyes,
        "eye_radius": number("eye_radius", 0.085, 0.02, 0.35),
        "eye_period": number("eye_period", 4.6, 1.0, 30.0),
        "lines": lines if isinstance(lines, str) else "",
        "lines_glow": number("lines_glow", 0.20, 0.02, 0.60),
        "lines_band": number("lines_band", 0.85, 0.20, 1.0),
        "particles": bool(value.get("particles", False)),
    }


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
        "avatar_animation": _clean_animation(
            record.get("avatar_animation")
        ),
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
    seen_ids: set[str] = set()

    for path in (
        model_files.MODELS_FILE,
        model_files.CUSTOM_MODELS_FILE,
    ):
        document = read_json_object(path)

        for record in document.get("models", []):
            model = _parse_model(record)

            if model is None or model["id"] in seen_ids:
                continue

            # Недоступные и нерабочие модели не показываем.
            if is_model_unavailable(model):
                continue

            models.append(model)
            seen_ids.add(model["id"])

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
