# Giperion/terminal/core/model_passport.py                           v001
# Паспорт модели: чтение JSON, компактные метрики и разделы для окна.
# Последнее изменение: первый вариант — паспорт Гипериона.

from config import DATA_DIR
from shared.storage.json_store import read_json
from terminal.core.passport_format import (
    UNKNOWN,  # noqa: F401 — реэкспорт для окна
    _counted,
    _section,
    _total_params,
    format_date,
    format_level,
    format_params,
    format_percent,
    passport_accuracy,  # noqa: F401 — реэкспорт для окна
    passport_level_code,  # noqa: F401 — реэкспорт для окна
)
from terminal.core.passport_sections import (
    passport_notes,  # noqa: F401 — реэкспорт для окна
    passport_sections,  # noqa: F401 — реэкспорт для окна
)

PASSPORTS_FILE = DATA_DIR / "model_passports.json"

# Что показываем, если в паспорте нет значения.


def load_passports() -> dict[str, dict]:
    """Читает паспорта моделей. При ошибке возвращает пустой словарь."""

    document = read_json(PASSPORTS_FILE, {})

    if not isinstance(document, dict):
        return {}

    passports = document.get("passports")

    if not isinstance(passports, dict):
        return {}

    return {
        str(model_id): passport
        for model_id, passport in passports.items()
        if isinstance(passport, dict)
    }


def get_passport(model_id: str) -> dict | None:
    """Возвращает паспорт модели или None, если его ещё нет."""

    return load_passports().get(model_id)


def compact_metrics(passport: dict) -> list[tuple[str, str]]:
    """Семь самых динамичных строк для левой панели."""

    architecture = _section(passport, "architecture")
    quality = _section(passport, "quality")

    context_text = _counted(
        architecture.get("context_tokens"),
        "токен",
        "токена",
        "токенов",
    )

    return [
        ("Уровень", format_level(passport)),
        ("Точность", format_percent(quality.get("accuracy"))),
        ("Macro-F1", format_percent(quality.get("macro_f1"))),
        ("Непонятых", format_percent(quality.get("fallback"))),
        ("Параметры", format_params(_total_params(architecture))),
        ("Контекст", context_text),
        ("Обновлён", format_date(passport.get("updated"))),
    ]
