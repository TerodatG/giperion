# Giperion/terminal/core/passport_format.py                           v001
# Форматирование чисел, дат и уровней паспорта.
# Последнее изменение: вынесено из model_passport.


UNKNOWN = "не измерено"


def _number(value: object) -> float | None:
    """Приводит значение к числу; None и мусор остаются None."""

    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def _integer(value: object) -> int | None:
    """Приводит значение к целому числу."""

    number = _number(value)

    return int(number) if number is not None else None


def _section(passport: dict, key: str) -> dict:
    """Возвращает вложенный раздел паспорта или пустой словарь."""

    value = passport.get(key)

    return value if isinstance(value, dict) else {}


def _decimal(value: float, digits: int = 1) -> str:
    """Пишет число с запятой вместо точки."""

    return f"{value:.{digits}f}".replace(".", ",")


def format_params(value: object) -> str:
    """Пишет число параметров: «691 469» или «2,9 млн»."""

    number = _integer(value)

    if number is None:
        return UNKNOWN

    if number >= 1_000_000:
        return _decimal(number / 1_000_000) + " млн"

    return f"{number:,}".replace(",", " ")


def format_percent(value: object, digits: int = 1) -> str:
    """Пишет долю как проценты: 0.64 → «64,0 %»."""

    number = _number(value)

    if number is None:
        return UNKNOWN

    return _decimal(number * 100, digits) + " %"


def format_number(value: object) -> str:
    """Пишет целое число с пробелами между разрядами."""

    number = _integer(value)

    if number is None:
        return UNKNOWN

    return f"{number:,}".replace(",", " ")


def format_date(value: object) -> str:
    """Переводит 2026-10-25 в 25.10.2026."""

    if not isinstance(value, str) or not value.strip():
        return UNKNOWN

    parts = value.strip().split("-")

    if len(parts) != 3:
        return value

    year, month, day = parts

    return f"{day}.{month}.{year}"


def format_level(passport: dict) -> str:
    """Собирает «L1 · секретарь-стажёр»."""

    level = _section(passport, "level")
    code = str(level.get("code") or "").strip()
    title = str(level.get("title") or "").strip()

    if code and title:
        return f"{code} · {title}"

    return code or title or UNKNOWN


def passport_accuracy(passport: dict | None) -> float | None:
    """Возвращает точность модели (0..1) или None."""

    if not isinstance(passport, dict):
        return None

    return _number(_section(passport, "quality").get("accuracy"))


def passport_level_code(passport: dict | None) -> str:
    """Возвращает код уровня («L1») или пустую строку."""

    if not isinstance(passport, dict):
        return ""

    return str(_section(passport, "level").get("code") or "").strip()


def _milliseconds(value: object) -> str:
    """Пишет миллисекунды с одним знаком."""

    number = _number(value)

    if number is None:
        return UNKNOWN

    return _decimal(number) + " мс"


def _seconds(value: object) -> str:
    """Пишет секунды с одним знаком."""

    number = _number(value)

    if number is None:
        return UNKNOWN

    return _decimal(number) + " с"


def _megabytes(value: object) -> str:
    """Пишет мегабайты с одним знаком."""

    number = _number(value)

    if number is None:
        return UNKNOWN

    return _decimal(number) + " МБ"


def _with_unit(value: object, unit: str) -> str:
    """Пишет целое число с единицей или «не измерено»."""

    number = _integer(value)

    if number is None:
        return UNKNOWN

    return format_number(number) + " " + unit


def plural(value: object, one: str, few: str, many: str) -> str:
    """Склоняет существительное по числу: 1 токен, 2 токена, 5 токенов."""

    number = _integer(value)

    if number is None:
        return many

    tail = abs(number) % 100

    if 11 <= tail <= 14:
        return many

    tail = tail % 10

    if tail == 1:
        return one

    if 2 <= tail <= 4:
        return few

    return many


def _counted(value: object, one: str, few: str, many: str) -> str:
    """Пишет число со склонённым словом."""

    number = _integer(value)

    if number is None:
        return UNKNOWN

    return format_number(number) + " " + plural(number, one, few, many)


def _total_params(architecture: dict) -> int | None:
    """Сумма параметров классификатора и генератора."""

    values = (
        _integer(architecture.get("classifier_params")),
        _integer(architecture.get("generator_params")),
    )
    known = [value for value in values if value is not None]

    if not known:
        return None

    return sum(known)

