# Giperion/terminal/core/model_passport.py                           v001
# Паспорт модели: чтение JSON, компактные метрики и разделы для окна.
# Последнее изменение: первый вариант — паспорт Гипериона.

from config import DATA_DIR
from shared.storage.json_store import read_json

PASSPORTS_FILE = DATA_DIR / "model_passports.json"

# Что показываем, если в паспорте нет значения.
UNKNOWN = "не измерено"


def load_passports() -> dict[str, dict]:
    """Читает паспорта моделей. При ошибке возвращает пустой словарь."""

    document = read_json(PASSPORTS_FILE, {})

    if not isinstance(document, dict):
        return {}

    passports = document.get("passports")

    if not isinstance(passports, dict):
        return {}

    return {
        str(model_id): passport
        for model_id, passport in passports.items()
        if isinstance(passport, dict)
    }


def get_passport(model_id: str) -> dict | None:
    """Возвращает паспорт модели или None, если его ещё нет."""

    return load_passports().get(model_id)


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


def compact_metrics(passport: dict) -> list[tuple[str, str]]:
    """Семь самых динамичных строк для левой панели."""

    architecture = _section(passport, "architecture")
    quality = _section(passport, "quality")

    context_text = _counted(
        architecture.get("context_tokens"),
        "токен",
        "токена",
        "токенов",
    )

    return [
        ("Уровень", format_level(passport)),
        ("Точность", format_percent(quality.get("accuracy"))),
        ("Macro-F1", format_percent(quality.get("macro_f1"))),
        ("Непонятых", format_percent(quality.get("fallback"))),
        ("Параметры", format_params(_total_params(architecture))),
        ("Контекст", context_text),
        ("Обновлён", format_date(passport.get("updated"))),
    ]


def _params_row(architecture: dict) -> str:
    """Строка «Параметры» с разбивкой по двум сетям."""

    classifier = _integer(architecture.get("classifier_params"))
    generator = _integer(architecture.get("generator_params"))
    total = _total_params(architecture)

    if classifier is None and generator is None:
        return UNKNOWN

    return (
        f"{format_params(total)} (классификатор "
        f"{format_params(classifier)}, генератор "
        f"{format_params(generator)})"
    )


def _data_row(training: dict) -> str:
    """Строка «Данные»: фразы, намерения и пары."""

    return " · ".join(
        (
            _counted(training.get("patterns"), "фраза", "фразы", "фраз"),
            _counted(
                training.get("intents"),
                "намерение",
                "намерения",
                "намерений",
            ),
            _counted(training.get("pairs"), "пара", "пары", "пар"),
        )
    )


def _eval_row(training: dict) -> str:
    """Строка «Отложенный набор»."""

    return (
        _counted(
            training.get("eval_phrases"),
            "фраза",
            "фразы",
            "фраз",
        )
        + " ("
        + format_number(training.get("eval_usable"))
        + " пригодных)"
    )


def _accuracy_row(quality: dict) -> str:
    """Строка точности с числом верных ответов."""

    return (
        f"{format_percent(quality.get('accuracy'))} "
        f"({format_number(quality.get('accuracy_correct'))} из "
        f"{format_number(quality.get('accuracy_total'))})"
    )


def _ci_row(quality: dict) -> str:
    """Строка доверительного интервала."""

    ci = _number(quality.get("ci"))

    if ci is None:
        return UNKNOWN

    return "±" + f"{ci * 100:.0f}" + " п.п."


def _vocab_row(architecture: dict) -> str:
    """Строка словаря."""

    return " · ".join(
        (
            _counted(
                architecture.get("vocab_words"),
                "слово",
                "слова",
                "слов",
            ),
            _counted(
                architecture.get("vocab_chars"),
                "символ",
                "символа",
                "символов",
            ),
        )
    )


def _modalities_text(architecture: dict) -> str:
    """Описывает вход и выход модели, если они известны."""

    titles = {
        "text": "текст",
        "image": "изображения",
        "video": "видео",
        "audio": "аудио",
        "pdf": "PDF",
    }

    parts = []

    for key, title in (("input", "вход"), ("output", "выход")):
        values = architecture.get(key)

        if not isinstance(values, list) or not values:
            continue

        names = ", ".join(
            titles.get(str(value), str(value))
            for value in values
        )
        parts.append(f"{title}: {names}")

    return " · ".join(parts)


def _architecture_rows(
    architecture: dict,
    training: dict,
) -> list[tuple[str, str]]:
    """Строки раздела «Паспорт» — только известные значения."""

    rows: list[tuple[str, str]] = []

    if architecture.get("kind"):
        rows.append(("Тип", str(architecture["kind"])))

    if (
        architecture.get("classifier_params") is not None
        or architecture.get("generator_params") is not None
    ):
        rows.append(("Параметры", _params_row(architecture)))

    if architecture.get("size_mb") is not None:
        rows.append(
            ("Размер", _megabytes(architecture.get("size_mb")))
        )

    if architecture.get("context_tokens") is not None:
        rows.append(
            (
                "Контекст",
                _counted(
                    architecture.get("context_tokens"),
                    "токен",
                    "токена",
                    "токенов",
                ),
            )
        )

    if architecture.get("output_tokens") is not None:
        rows.append(
            (
                "Выход модели",
                _counted(
                    architecture.get("output_tokens"),
                    "токен",
                    "токена",
                    "токенов",
                ),
            )
        )

    if (
        architecture.get("vocab_words") is not None
        or architecture.get("vocab_chars") is not None
    ):
        rows.append(("Словарь", _vocab_row(architecture)))

    if architecture.get("classes") is not None:
        rows.append(
            ("Классы", format_number(architecture.get("classes")))
        )

    modalities = _modalities_text(architecture)

    if modalities:
        rows.append(("Модальности", modalities))

    if training:
        rows.append(("Данные", _data_row(training)))
        rows.append(("Отложенный набор", _eval_row(training)))

    return rows


def _access_rows(access: dict) -> list[tuple[str, str]]:
    """Строки раздела «Доступ»."""

    rows = []

    for key, title in (
        ("provider", "Провайдер"),
        ("api", "Канал"),
        ("price", "Цена и лимит"),
        ("status", "Статус"),
        ("url", "Сайт"),
    ):
        value = access.get(key)

        if value:
            rows.append((title, str(value)))

    return rows


def _feature_rows(features: dict) -> list[tuple[str, str]]:
    """Строки раздела «Функции»: да/нет по известным флагам."""

    rows = []

    for key, title in (
        ("reasoning", "Рассуждения"),
        ("tools", "Инструменты"),
        ("structured", "Структурированный вывод"),
        ("vision", "Изображения"),
        ("pdf", "PDF"),
        ("video", "Видео"),
        ("audio", "Аудио"),
        ("temperature", "Температура"),
    ):
        if key in features:
            rows.append(
                (title, "да" if features.get(key) else "нет")
            )

    return rows


def passport_sections(
    passport: dict,
) -> list[tuple[str, list[tuple[str, str]]]]:
    """Собирает разделы окна «Параметры ИИ» из паспорта."""

    architecture = _section(passport, "architecture")
    training = _section(passport, "training")
    quality = _section(passport, "quality")
    dialogue = _section(passport, "dialogue")
    speed = _section(passport, "speed")
    dynamics = _section(passport, "dynamics")
    access = _section(passport, "access")
    features = _section(passport, "features")

    sections: list[tuple[str, list[tuple[str, str]]]] = []

    if _section(passport, "level"):
        sections.append(
            (
                "УРОВЕНЬ",
                [
                    ("Уровень", format_level(passport)),
                    ("Обновлён", format_date(passport.get("updated"))),
                ],
            )
        )

    architecture_rows = _architecture_rows(architecture, training)

    if architecture_rows:
        sections.append(("ПАСПОРТ", architecture_rows))

    access_rows = _access_rows(access)

    if access_rows:
        sections.append(("ДОСТУП", access_rows))

    feature_rows = _feature_rows(features)

    if feature_rows:
        sections.append(("ФУНКЦИИ", feature_rows))

    if quality:
        sections.append(
            (
                "КАЧЕСТВО",
                [
                    ("Точность (top-1)", _accuracy_row(quality)),
                    ("Macro-F1", format_percent(quality.get("macro_f1"))),
                    ("Доверительный интервал", _ci_row(quality)),
                    (
                        "Средняя уверенность",
                        format_percent(
                            quality.get("mean_confidence")
                        ),
                    ),
                    (
                        "Калибровка (ECE)",
                        format_percent(quality.get("ece")),
                    ),
                    (
                        "Fallback",
                        format_percent(quality.get("fallback")),
                    ),
                    (
                        "Точность на опечатках",
                        format_percent(quality.get("noise_accuracy")),
                    ),
                    (
                        "OOD-детекция",
                        format_percent(quality.get("ood_auroc")),
                    ),
                ],
            )
        )

    if dialogue:
        sections.append(
            (
                "ДИАЛОГ И КОНТЕКСТ",
                [
                    (
                        "Multi-turn (3 хода)",
                        format_percent(dialogue.get("multi_turn")),
                    ),
                    (
                        "Использование контекста",
                        str(
                            dialogue.get("context_utilization")
                            or UNKNOWN
                        ),
                    ),
                    (
                        "Retention после обучения",
                        format_percent(dialogue.get("retention")),
                    ),
                ],
            )
        )

    if speed:
        sections.append(
            (
                "СКОРОСТЬ И РЕСУРСЫ",
                [
                    ("p50 ответа", _milliseconds(speed.get("p50_ms"))),
                    ("p95 ответа", _milliseconds(speed.get("p95_ms"))),
                    (
                        "Устройство",
                        str(speed.get("device") or UNKNOWN),
                    ),
                    (
                        "Холодный старт",
                        _seconds(speed.get("cold_start_s")),
                    ),
                    (
                        "Память",
                        _with_unit(speed.get("ram_mb"), "МБ"),
                    ),
                    (
                        "Стоимость 1000 запросов",
                        str(speed.get("cost") or UNKNOWN),
                    ),
                ],
            )
        )

    if dynamics:
        sections.append(
            (
                "ДИНАМИКА",
                [
                    (
                        "Data efficiency",
                        format_percent(
                            dynamics.get("data_efficiency")
                        ),
                    ),
                    (
                        "Time-to-fix",
                        _with_unit(
                            dynamics.get("time_to_fix_days"),
                            "дн.",
                        ),
                    ),
                    (
                        "Coverage",
                        format_percent(dynamics.get("coverage")),
                    ),
                    (
                        "Качество разметки",
                        format_percent(
                            dynamics.get("label_quality")
                        ),
                    ),
                ],
            )
        )

    return sections


def passport_notes(passport: dict) -> list[str]:
    """Возвращает заметки паспорта без пустых строк."""

    notes = passport.get("notes")

    if not isinstance(notes, list):
        return []

    return [
        str(note).strip()
        for note in notes
        if isinstance(note, str) and note.strip()
    ]

