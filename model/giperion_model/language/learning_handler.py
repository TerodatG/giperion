# Giperion/app/language/learning_handler.py                     v008
# Совместимый фасад команд обучения и текстов категорий.
# Последнее изменение: реализация разделена на learning_commands и learning_presenter.

from giperion_model.language.learning_commands import (
    get_learning_response,
)
from giperion_model.language.learning_presenter import (
    CATEGORY_DESCRIPTIONS,
    get_categories_response,
    get_category_description,
    split_category_description,
)

__all__ = [
    "CATEGORY_DESCRIPTIONS",
    "get_categories_response",
    "get_category_description",
    "get_learning_response",
    "split_category_description",
]
