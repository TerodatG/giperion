# Giperion/app/core/evolution_service.py                            v001
# Опыт, уровни и ранги Гипериона как развивающегося персонажа.
# Последнее изменение: первый вариант — экспоненциальные пороги и динамические тип/версия.

import math

from giperion_model.identity_matrix import IDENTITY_MATRIX
from giperion_model.language.learning_service import get_available_categories

from terminal.memory.memory import (
    get_messages_count,
    get_unknown_messages,
)

# --- Вес источников опыта ---
# Каждое действие даёт очки опыта. Чем важнее вклад в развитие, тем больше вес.
# Навыки — врождённый набор, он почти не растёт, поэтому вес небольшой:
# основную динамику дают память, знания и разобранные фразы.

SKILL_WEIGHT = 15      # каждый освоенный навык
CATEGORY_WEIGHT = 40   # каждая выученная категория знаний
MEMORY_WEIGHT = 1      # каждое сохранённое сообщение
LEARNED_WEIGHT = 60    # каждая разобранная непонятая фраза
UNKNOWN_WEIGHT = -3    # штраф за фразу, которую пока не понимаем

# --- Порог первого уровня и множитель роста ---
# Пороги уровней растут экспоненциально: чем выше уровень,
# тем заметно дольше до следующего. Поэтому прогресс виден надолго.
BASE_THRESHOLD = 120
GROWTH_FACTOR = 1.55

# Версия ядра поднимается каждые CORE_VERSION_STEP уровней.
CORE_VERSION_STEP = 3
CORE_VERSION_BASE = 0.1


def total_threshold(level: int) -> int:
    """Сумма опыта, нужная для достижения уровня (1 — первый)."""

    if level <= 1:
        return 0

    return int(
        BASE_THRESHOLD
        * (math.pow(GROWTH_FACTOR, level - 1) - 1)
        / (GROWTH_FACTOR - 1)
    )


def get_learned_count() -> int:
    """Считает фразы, которые Гиперион освоил через обучение.

    Оценка: сколько фраз добавлено в намерения сверх базового набора.
    """

    categories = get_available_categories()

    return max(0, len(categories) - BASELINE_CATEGORIES)


# Базовое число категорий проекта — до пользовательского обучения.
# Нужно, чтобы отделить врождённые знания от выученных.
BASELINE_CATEGORIES = 77


def get_experience_breakdown() -> dict[str, int]:
    """Раскладывает общий опыт по источникам развития."""

    skills_count = len(IDENTITY_MATRIX["skills"])
    memory_records_count = get_messages_count()
    unknown_messages_count = len(get_unknown_messages())
    learned_count = get_learned_count()

    return {
        "skills": skills_count * SKILL_WEIGHT,
        "knowledge": learned_count * CATEGORY_WEIGHT,
        "memory": memory_records_count * MEMORY_WEIGHT,
        "learned": learned_count * LEARNED_WEIGHT,
        "unknown": unknown_messages_count * UNKNOWN_WEIGHT,
    }


def get_total_experience() -> int:
    """Считает общий опыт, никогда не опускаясь ниже нуля."""

    return max(0, sum(get_experience_breakdown().values()))


def get_level_for_experience(experience: int) -> int:
    """Определяет уровень по накопленному опыту."""

    level = 1

    while total_threshold(level + 1) <= experience:
        level += 1

    return level


def get_level_progress(experience: int) -> dict[str, int]:
    """Возвращает уровень и прогресс внутри него."""

    level = get_level_for_experience(experience)

    current_floor = total_threshold(level)
    next_ceiling = total_threshold(level + 1)

    span = next_ceiling - current_floor
    progress = experience - current_floor

    percent = int(progress * 100 / span) if span else 0

    return {
        "level": level,
        "current": current_floor,
        "next": next_ceiling,
        "progress": progress,
        "span": span,
        "percent": percent,
        "remaining": max(0, next_ceiling - experience),
    }


def get_core_version(level: int) -> str:
    """Версия ядра растёт ступенями вместе с уровнем."""

    step = max(0, (level - 1) // CORE_VERSION_STEP)

    return f"{CORE_VERSION_BASE + step * 0.1:.1f}"


# Названия этапов развития по уровню.
RANK_NAMES = (
    (1, "Пробуждение"),
    (3, "Новичок"),
    (6, "Ученик"),
    (10, "Собеседник"),
    (15, "Знаток"),
    (22, "Наставник"),
    (30, "Мудрец"),
)


def get_rank_name(level: int) -> str:
    """Возвращает название этапа развития по уровню."""

    name = RANK_NAMES[0][1]

    for threshold, rank_name in RANK_NAMES:
        if level >= threshold:
            name = rank_name

    return name


# Динамический тип ядра по уровню.
SYSTEM_TYPES = (
    (1, "пробуждающийся ИИ-собеседник"),
    (4, "растущий ИИ-собеседник"),
    (10, "развитый ИИ-собеседник"),
    (18, "продвинутое ИИ-ядро"),
    (28, "зрелое ИИ-ядро"),
)


def get_system_type(level: int) -> str:
    """Возвращает тип ядра, растущий вместе с уровнем."""

    system_type = SYSTEM_TYPES[0][1]

    for threshold, type_name in SYSTEM_TYPES:
        if level >= threshold:
            system_type = type_name

    return system_type
