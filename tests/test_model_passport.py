# Giperion/tests/test_model_passport.py                             v001
# Паспорт модели: чтение, форматирование и разделы окна.

import json

from terminal.core import model_passport
from terminal.core.model_passport import (
    compact_metrics,
    format_date,
    format_params,
    format_percent,
    get_passport,
    passport_accuracy,
    passport_level_code,
    passport_notes,
    passport_sections,
)


def test_passport_of_giperion_is_readable() -> None:
    """У Гипериона есть паспорт с уровнем и качеством."""

    passport = get_passport("giperion")

    assert passport is not None
    assert passport_level_code(passport) == "L1"
    assert passport_accuracy(passport) == 0.839


def test_missing_passport_returns_none() -> None:
    """Для модели без паспорта окно покажет данные каталога."""

    assert get_passport("нет-такой-модели") is None


def test_compact_metrics_are_seven_dynamic_rows() -> None:
    """Левая панель получает ровно семь строк."""

    metrics = compact_metrics(get_passport("giperion"))
    values = dict(metrics)

    assert len(metrics) == 7
    assert values["Уровень"] == "L1 · секретарь-стажёр"
    assert values["Точность"] == "83,9 %"
    assert values["Параметры"] == "2,9 млн"
    assert values["Контекст"] == "32 токена"
    assert values["Обновлён"] == "28.10.2026"


def test_sections_cover_passport_and_quality() -> None:
    """Окно получает разделы паспорта и качества."""

    sections = passport_sections(get_passport("giperion"))
    titles = [title for title, _ in sections]
    rows = {
        name: value
        for _, section_rows in sections
        for name, value in section_rows
    }

    assert titles == [
        "УРОВЕНЬ",
        "ПАСПОРТ",
        "КАЧЕСТВО",
        "ДИАЛОГ И КОНТЕКСТ",
        "СКОРОСТЬ И РЕСУРСЫ",
        "ДИНАМИКА",
    ]
    assert "2,9 млн" in rows["Параметры"]
    assert rows["Точность (top-1)"].startswith("83,9 %")
    assert rows["Калибровка (ECE)"] == "не измерено"
    assert rows["p95 ответа"] == "1,6 мс"


def test_notes_are_clean() -> None:
    """Заметки отдаются без пустых строк и мусора."""

    passport = get_passport("giperion")
    notes = passport_notes(passport)

    assert notes
    assert all(isinstance(note, str) and note for note in notes)


def test_formatting_helpers() -> None:
    """Числа, проценты и даты пишутся по-русски."""

    assert format_params(691469) == "691 469"
    assert format_params(2205108) == "2,2 млн"
    assert format_params(None) == "не измерено"
    assert format_percent(0.64) == "64,0 %"
    assert format_percent(None) == "не измерено"
    assert format_date("2026-10-25") == "25.10.2026"
    assert format_date(None) == "не измерено"


def test_broken_file_gives_empty_passports(
    tmp_path,
    monkeypatch,
) -> None:
    """Битый JSON не роняет окно: паспортов просто нет."""

    broken = tmp_path / "passports.json"
    broken.write_text("{это не json", encoding="utf-8")

    monkeypatch.setattr(model_passport, "PASSPORTS_FILE", broken)

    assert model_passport.load_passports() == {}
    assert get_passport("giperion") is None


def test_passport_without_sections_is_safe(
    tmp_path,
    monkeypatch,
) -> None:
    """Пустой паспорт не ломает метрики и не рисует пустых плит."""

    document = {"passports": {"giperion": {}}}
    path = tmp_path / "passports.json"
    path.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(model_passport, "PASSPORTS_FILE", path)

    metrics = compact_metrics(get_passport("giperion"))

    assert len(metrics) == 7
    assert all(value == "не измерено" for _, value in metrics)
    assert passport_sections(get_passport("giperion")) == []


def test_external_model_has_catalog_passport() -> None:
    """У внешней модели есть разделы доступа и функций, но нет качества."""

    passport = get_passport("deepseek-v4.1-flash-free")

    assert passport is not None

    sections = passport_sections(passport)
    titles = [title for title, _ in sections]
    rows = {
        name: value
        for _, section_rows in sections
        for name, value in section_rows
    }

    assert "ПАСПОРТ" in titles
    assert "ДОСТУП" in titles
    assert "ФУНКЦИИ" in titles
    assert "КАЧЕСТВО" not in titles
    assert rows["Провайдер"] == "OpenCode"
    assert rows["Контекст"] == "200 000 токенов"
    assert rows["Изображения"] == "да"
    assert rows["Видео"] == "нет"


def test_every_catalog_model_has_passport() -> None:
    """Паспорт заполнен для всех моделей каталога."""

    from terminal.core.model_registry import load_models

    catalog_ids = {model["id"] for model in load_models()}
    passport_ids = set(model_passport.load_passports())

    assert catalog_ids <= passport_ids
