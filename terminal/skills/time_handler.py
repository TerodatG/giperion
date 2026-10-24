# Giperion/app/skills/time_handler.py                             v001
# Обработка команд времени, даты и дня недели Giperion.
# Последнее изменение: файл перемещён в пакет skills и обновлены импорты.

from terminal.core.phrases import (
    DATE_PHRASES,
    DAY_PHRASES,
    TIME_PHRASES,
)
from terminal.skills.time_service import (
    get_current_date,
    get_current_time,
    get_current_weekday,
)


def get_time_and_date_response(message: str) -> str | None:
    """Возвращает ответ на вопрос о времени, дате или дне недели."""

    if any(phrase in message for phrase in TIME_PHRASES):
        return f"Сейчас {get_current_time()}."

    if any(phrase in message for phrase in DATE_PHRASES):
        return f"Сегодня {get_current_date()}."

    if any(phrase in message for phrase in DAY_PHRASES):
        return f"Сегодня {get_current_weekday()}."

    return None
