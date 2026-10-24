# Giperion/app/ui/value_text.py                                   v002
# Текстовые представления чисел, моделей и функций для окна.
# Последнее изменение: умения модели и отказ от сравнения с каталогом.

from app.core.model_catalog import DEFAULT_STRENGTHS
from app.core.model_registry import build_stars, get_reputation

CAPABILITY_FEATURES = (
    ("text", "Текст и диалог"),
    ("reasoning", "Рассуждения"),
    ("tools", "Вызов инструментов"),
    ("structured", "Структурированный вывод"),
    ("vision", "Изображения"),
    ("pdf", "PDF и документы"),
    ("video", "Видео"),
    ("audio", "Аудио"),
    ("temperature", "Настройка температуры"),
    ("context", "Длинный контекст"),
)

MODALITY_TITLES = {
    "text": "текст",
    "image": "изображения",
    "video": "видео",
    "audio": "аудио",
    "pdf": "PDF",
}


def make_progress_bar(percent: int, width: int = 10) -> str:
    """Рисует текстовый прогресс-бар роста для окна."""

    filled = round(width * percent / 100)

    return "▰" * filled + "▱" * (width - filled)


def build_model_item_text(
    model: dict,
    current_id: str,
    companion_ids: set[str] | list[str] = (),
) -> str:
    """Собирает подпись модели для списка: имя, репутация, состояние."""

    reputation = get_reputation(model["id"])

    if model["id"] == current_id:
        state = "активна"
    elif model["group"] == "own":
        state = "своя"
    elif not model["available"]:
        state = "не подключена"
    else:
        state = "доступна"

    companion_mark = (
        " · компаньон"
        if model["id"] in companion_ids
        else ""
    )

    return (
        f"{model['name']}  {build_stars(reputation['stars'])}\n"
        f"{reputation['requests']} обращений · {state}"
        f"{companion_mark}"
    )


def format_tokens(value: int) -> str:
    """Пишет число токенов с пробелами между разрядами."""

    return f"{value:,}".replace(",", " ")


def tokens_word(value: int) -> str:
    """Склоняет слово «токен» по числу."""

    tail = value % 100

    if 11 <= tail <= 14:
        return "токенов"

    tail = value % 10

    if tail == 1:
        return "токен"

    if 2 <= tail <= 4:
        return "токена"

    return "токенов"


def format_percent(value: float) -> str:
    """Процент бюджета: целый или с десятой долей."""

    if value >= 10:
        return str(round(value))

    return f"{value:.1f}".replace(".", ",")


def model_capabilities(model: dict) -> dict:
    """Возвращает описание функций модели из каталога."""

    capabilities = model.get("capabilities")

    if isinstance(capabilities, dict):
        return capabilities

    return {}


def capability_score(model: dict, key: str) -> int:
    """Оценивает функцию модели по шкале 0–5 для сравнения."""

    capabilities = model_capabilities(model)

    if key == "text":
        strengths = model.get("strengths") or {}

        return int(strengths.get("Текст", 0) or 0)

    if key == "context":
        context = int(
            model.get("context_limit")
            or (capabilities.get("limit") or {}).get("context")
            or 0
        )

        if context >= 1_000_000:
            return 5

        if context >= 500_000:
            return 4

        if context >= 200_000:
            return 3

        if context >= 100_000:
            return 2

        return 1 if context > 0 else 0

    modalities = capabilities.get("modalities") or {}
    inputs = modalities.get("input") or []

    if key == "vision":
        return 5 if "image" in inputs else 0

    if key == "pdf":
        return 5 if "pdf" in inputs else 0

    if key == "video":
        return 4 if "video" in inputs else 0

    if key == "audio":
        return 4 if "audio" in inputs else 0

    flags = {
        "reasoning": "reasoning",
        "tools": "tool_call",
        "structured": "structured_output",
        "temperature": "temperature",
    }

    flag = flags.get(key)

    if flag and capabilities.get(flag):
        return 5

    return 0


def capability_value_text(model: dict, key: str) -> str:
    """Коротко показывает значение функции в таблице."""

    score = capability_score(model, key)

    if key in ("text", "context"):
        return f"{score}/5"

    return "да" if score else "нет"


def model_modalities_text(model: dict) -> str:
    """Описывает входные и выходные форматы модели."""

    capabilities = model_capabilities(model)

    if not capabilities:
        return "Функции пока не указаны."

    modalities = capabilities.get("modalities") or {}
    inputs = modalities.get("input") or []
    outputs = modalities.get("output") or []

    def titles(values: list[str]) -> str:
        names = [
            MODALITY_TITLES.get(value, value)
            for value in values
        ]

        return ", ".join(names) if names else "не указано"

    return (
        f"Вход: {titles(inputs)} · "
        f"Выход: {titles(outputs)}"
    )


def model_skill_entries(model: dict) -> list[dict]:
    """Собирает умения модели из её карточки: сильные стороны и функции."""

    entries = []
    strengths = model.get("strengths") or {}

    for strength in DEFAULT_STRENGTHS:
        try:
            value = int(strengths.get(strength, 0) or 0)
        except (TypeError, ValueError):
            value = 0

        if value > 0:
            entries.append(
                {
                    "name": strength,
                    "description": f"Оценка {value}/5.",
                }
            )

    seen = {entry["name"].casefold() for entry in entries}

    for key, title in CAPABILITY_FEATURES:
        if key == "text":
            # «Текст» уже показан в сильных сторонах.
            continue

        score = capability_score(model, key)

        if score <= 0 or title.casefold() in seen:
            continue

        entries.append(
            {
                "name": title,
                "description": (
                    f"{capability_value_text(model, key)} "
                    "по шкале возможностей."
                ),
            }
        )

    if not entries:
        entries.append(
            {
                "name": "Умения не указаны",
                "description": (
                    "В карточке модели нет положительных оценок."
                ),
            }
        )

    return entries
