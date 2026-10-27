# Giperion/tests/test_i18n.py                                          v001
# Локализация: выбор языка, словарь и подстановка.

from terminal.ui import i18n


def test_default_is_russian(monkeypatch) -> None:
    """Без GIPERION_LANG интерфейс русский."""

    monkeypatch.delenv("GIPERION_LANG", raising=False)

    assert i18n.current_language() == "ru"
    assert i18n.tr("knowledge.title") == "База знаний"


def test_english_environment(monkeypatch) -> None:
    """GIPERION_LANG=en переключает строки."""

    monkeypatch.setenv("GIPERION_LANG", "en")

    assert i18n.current_language() == "en"
    assert i18n.tr("knowledge.search") == "Search"


def test_unknown_language_falls_back(monkeypatch) -> None:
    """Неизвестный язык не ломает интерфейс."""

    monkeypatch.setenv("GIPERION_LANG", "de")

    assert i18n.current_language() == "ru"


def test_format_and_unknown_key(monkeypatch) -> None:
    """Подстановка работает, неизвестный ключ возвращается как есть."""

    monkeypatch.setenv("GIPERION_LANG", "en")

    assert "a.md" in i18n.tr(
        "knowledge.delete_question",
        path="a.md",
    )
    assert i18n.tr("unknown.key") == "unknown.key"
