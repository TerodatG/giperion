# Giperion/app/core/conference_roster.py                            v001
# Состав сената: не больше трёх моделей и должности сенаторов.
# Последнее изменение: отбор по репутации и нумерация сенаторов.

from terminal.core.model_stats import get_reputation

# В совет пускаются не больше трёх моделей, включая Гипериона.
MAX_CONFERENCE_MODELS = 3

# Группы шрифта для должностей совета.
SENATOR_ROLES = (
    "senator1",
    "senator2",
    "senator3",
)


def reputation_requests(model_id: str) -> int:
    """Число обращений к модели — мера репутации."""

    reputation = get_reputation(model_id)

    try:
        return int(reputation.get("requests", 0) or 0)
    except (TypeError, ValueError):
        return 0


def order_models_by_reputation(
    models: list[dict],
) -> list[dict]:
    """Сортирует модели от самой высокой репутации к низшей."""

    return sorted(
        models,
        key=lambda model: -reputation_requests(model["id"]),
    )


def select_conference_models(
    models: list[dict],
) -> list[dict]:
    """Оставляет в сенате трёх участников с лучшей репутацией."""

    return order_models_by_reputation(models)[
        :MAX_CONFERENCE_MODELS
    ]


def senator_role(number: int) -> str:
    """Группа шрифта для должности «Сенатор N»."""

    if 1 <= number <= len(SENATOR_ROLES):
        return SENATOR_ROLES[number - 1]

    return "external"


def senator_title(number: int) -> str:
    """Подпись должности для списков и карточек."""

    if 1 <= number <= MAX_CONFERENCE_MODELS:
        return f"Сенатор {number}"

    return "Резерв"
