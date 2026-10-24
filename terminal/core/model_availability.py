# Giperion/app/core/model_availability.py                           v001
# Модели OpenCode, которые нельзя использовать из России.
# Последнее изменение: проверка каталога запросами от 2026-10-24.

# Страновые ограничения: OpenCode ответил
# «This model is not available in your country» или
# «Country, region, or territory not supported».
REGION_BLOCKED_IDS = frozenset(
    {
        "beam-free",
        "gpt-5.6-luna",
        "gpt-6-luna",
        "muse-spark-1.2-contributor",
        "muse-spark-1.3-contributor",
    }
)

# Модели, которые OpenCode не обслуживает: неподдерживаемый идентификатор
# или выключенный endpoint. Они тоже не должны попадать в список.
BROKEN_MODEL_IDS = frozenset(
    {
        "mimo-v2.5",
        "mimo-v2.5-pro",
        "grok-4.7",
        "gemini-4-argon-contributor",
    }
)

UNAVAILABLE_MODEL_IDS = (
    REGION_BLOCKED_IDS | BROKEN_MODEL_IDS
)


def is_model_unavailable(model: dict) -> bool:
    """True, если модель нельзя использовать в этом окружении."""

    if not model.get("provider_id"):
        # Своё ядро и локальные модели ограничений не имеют.
        return False

    open_code_id = model.get("model_id") or model.get("id") or ""

    return str(open_code_id) in UNAVAILABLE_MODEL_IDS
