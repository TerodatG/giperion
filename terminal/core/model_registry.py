# Giperion/app/core/model_registry.py                              v013
# Совместимый фасад каталога моделей, настроек и статистики.
# Последнее изменение: удаление своей модели через фасад.

from terminal.core.model_catalog import (
    COMPANION_GROUP,
    CONFERENCE_GROUP,
    DEFAULT_MODEL_ID,
    DEFAULT_STRENGTHS,
    MODEL_GROUPS,
    get_model,
    load_models,
)
from terminal.core.model_custom import (
    add_custom_model,
    remove_custom_model,
)
from terminal.core.model_settings import (
    get_active_model,
    get_current_model_id,
    get_models_by_group,
    is_companion,
    is_conference_member,
    load_companion_ids,
    load_conference_ids,
    save_companion_ids,
    save_conference_ids,
    set_companion,
    set_conference_member,
    set_current_model_id,
)
from terminal.core.model_stats import (
    build_stars,
    get_reputation,
    get_usage,
    load_stats,
    record_model_request,
    save_stats,
)

__all__ = [
    "COMPANION_GROUP",
    "CONFERENCE_GROUP",
    "DEFAULT_MODEL_ID",
    "DEFAULT_STRENGTHS",
    "MODEL_GROUPS",
    "add_custom_model",
    "build_stars",
    "get_active_model",
    "get_current_model_id",
    "get_model",
    "get_models_by_group",
    "get_reputation",
    "get_usage",
    "is_companion",
    "is_conference_member",
    "load_companion_ids",
    "load_conference_ids",
    "load_models",
    "load_stats",
    "record_model_request",
    "save_companion_ids",
    "save_conference_ids",
    "save_stats",
    "set_companion",
    "set_conference_member",
    "set_current_model_id",
]
