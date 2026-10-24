# Giperion/app/core/model_stats.py                                 v001
# Обращения к моделям, расход токенов, репутация и лимиты.
# Последнее изменение: выделено из model_registry.

from terminal.core import model_files
from terminal.core.model_catalog import get_model
from shared.storage.json_store import read_json_object, write_json


def load_stats() -> dict[str, dict[str, int]]:
    """Обращения и израсходованные токены по каждой модели."""

    document = read_json_object(model_files.STATS_FILE)
    stats = {}

    for model_id, record in document.get("models", {}).items():
        if not isinstance(record, dict):
            continue

        requests = record.get("requests", 0)
        tokens = record.get("tokens", 0)

        stats[model_id] = {
            "requests": requests if isinstance(requests, int) else 0,
            "tokens": tokens if isinstance(tokens, int) else 0,
        }

    return stats


def save_stats(stats: dict[str, dict[str, int]]) -> None:
    """Записывает обращения и расход токенов."""

    document = {
        "models": {
            model_id: {
                "requests": record.get("requests", 0),
                "tokens": record.get("tokens", 0),
            }
            for model_id, record in sorted(stats.items())
        }
    }

    write_json(model_files.STATS_FILE, document)


def record_model_request(
    model_id: str,
    tokens: int = 0,
) -> dict[str, int]:
    """Считает обращение и израсходованные токены."""

    stats = load_stats()
    record = stats.get(model_id, {"requests": 0, "tokens": 0})

    record["requests"] += 1
    record["tokens"] += max(0, int(tokens))
    stats[model_id] = record

    save_stats(stats)

    return record


def get_reputation(model_id: str) -> dict:
    """Репутация модели: обращения, звёзды (0–5) и заполнение шкалы.

    Шкала считается относительно самой популярной модели: у лидера
    всегда 100 % и пять звёзд, у остальных — доля от его числа.
    """

    stats = load_stats()
    requests = stats.get(model_id, {}).get("requests", 0)
    best = max(
        (
            record.get("requests", 0)
            for record in stats.values()
        ),
        default=0,
    )

    if best <= 0 or requests <= 0:
        return {"requests": requests, "stars": 0, "percent": 0}

    percent = round(100 * requests / best)
    stars = max(1, min(5, int(5 * requests / best + 0.5)))

    return {
        "requests": requests,
        "stars": stars,
        "percent": percent,
    }


def get_usage(model_id: str) -> dict:
    """Расход токенов и лимиты модели для карточки."""

    model = get_model(model_id)
    used = load_stats().get(model_id, {}).get("tokens", 0)

    context_limit = model["context_limit"] if model else 0
    token_budget = model["token_budget"] if model else 0
    available = max(0, token_budget - used)

    return {
        "context_limit": context_limit,
        "token_budget": token_budget,
        "tokens_used": used,
        "tokens_available": available,
        "percent": (
            round(100 * used / token_budget)
            if token_budget > 0
            else 0
        ),
    }


def build_stars(stars: int) -> str:
    """Рисует шкалу репутации звёздами: заполненные и пустые."""

    filled = max(0, min(5, int(stars)))

    return "★" * filled + "☆" * (5 - filled)
