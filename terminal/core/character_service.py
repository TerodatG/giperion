# Giperion/app/core/character_service.py                          v002
# Сбор характеристик ИИ-ядра Giperion (персонаж и его развитие).
# Последнее изменение: уровень, тип и версия ядра стали динамическими.

from giperion_model.identity_matrix import IDENTITY_MATRIX
from terminal.core.evolution_service import (
    get_core_version,
    get_experience_breakdown,
    get_level_progress,
    get_rank_name,
    get_system_type,
    get_total_experience,
)
from terminal.memory.memory import (
    get_messages_count,
    get_unknown_messages,
)


def get_development_level(experience: int) -> str:
    """Собирает подпись уровня: номер, этап и прогресс до следующего."""

    progress = get_level_progress(experience)

    rank = get_rank_name(progress["level"])

    return (
        f"{progress['level']} — {rank} "
        f"({progress['percent']}% до след.)"
    )


def get_characteristics() -> dict[str, str | int]:
    """Собирает текущие характеристики ИИ-ядра для окна и команд."""

    skills_count = len(IDENTITY_MATRIX["skills"])
    memory_records_count = get_messages_count()
    unknown_messages_count = len(get_unknown_messages())

    experience = get_total_experience()
    progress = get_level_progress(experience)

    return {
        "identifier": IDENTITY_MATRIX["identifier"],
        "system_type": get_system_type(progress["level"]),
        "core_version": get_core_version(progress["level"]),
        "level": get_development_level(experience),
        "evolution": experience,
        "experience": experience,
        "level_number": progress["level"],
        "level_percent": progress["percent"],
        "level_remaining": progress["remaining"],
        "breakdown": get_experience_breakdown(),
        "skills_count": skills_count,
        "memory_records_count": memory_records_count,
        "unknown_messages_count": unknown_messages_count,
        "status": "активно",
    }
