# Giperion/app/skills/time_service.py                             v001
# Получение локальных времени, даты и дня недели Giperion.
# Последнее изменение: файл перемещён в пакет skills без изменения логики.

from datetime import datetime

WEEKDAYS = [
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
]

MONTHS = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]


def get_current_datetime() -> datetime:
    """Возвращает текущие локальные дату и время компьютера."""

    return datetime.now()


def get_current_time() -> str:
    """Возвращает текущее время в формате ЧЧ:ММ."""

    return get_current_datetime().strftime("%H:%M")


def get_current_date() -> str:
    """Возвращает текущую дату в русскоязычном формате."""

    current_datetime = get_current_datetime()

    return (
        f"{current_datetime.day} "
        f"{MONTHS[current_datetime.month - 1]} "
        f"{current_datetime.year} года"
    )


def get_current_weekday() -> str:
    """Возвращает текущий день недели на русском языке."""

    return WEEKDAYS[get_current_datetime().weekday()]