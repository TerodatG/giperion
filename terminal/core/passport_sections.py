# Giperion/terminal/core/passport_sections.py                         v001
# Разделы паспорта: архитектура, доступ, функции и заметки.
# Последнее изменение: вынесено из model_passport.

from terminal.core.passport_format import (
    UNKNOWN,
    _counted,
    _integer,
    _megabytes,
    _milliseconds,
    _number,
    _seconds,
    _section,
    _total_params,
    _with_unit,
    format_date,
    format_level,
    format_number,
    format_params,
    format_percent,
)


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

