# Giperion/terminal/ui/i18n.py                                         v001
# Локализация RU/EN: язык из GIPERION_LANG, словарь строк.
# Последнее изменение: первый вариант — tr и knowledge-строки.

import os

DEFAULT_LANGUAGE = "ru"
LANGUAGES = ("ru", "en")

TRANSLATIONS = {
    "ru": {
        "knowledge.title": "База знаний",
        "knowledge.hint": (
            "Документы из knowledge/ ищутся по смыслу. "
            "Цитата показывает файл и строку."
        ),
        "knowledge.search": "Найти",
        "knowledge.query": "Что найти?",
        "knowledge.add": "Добавить текст…",
        "knowledge.remove": "Удалить",
        "knowledge.close": "Закрыть",
        "knowledge.new": "Новый документ",
        "knowledge.text": "Текст:",
        "knowledge.header": "Заголовок",
        "knowledge.name": "Название:",
        "knowledge.tags": "Теги",
        "knowledge.tags_hint": "Через запятую (необязательно):",
        "knowledge.empty": "фрагмент пуст",
        "knowledge.delete": "Удалить документ",
        "knowledge.delete_question": "Удалить {path} из базы знаний?",
    },
    "en": {
        "knowledge.title": "Knowledge base",
        "knowledge.hint": (
            "Documents in knowledge/ are searched by meaning. "
            "A citation shows the file and line."
        ),
        "knowledge.search": "Search",
        "knowledge.query": "What to find?",
        "knowledge.add": "Add text…",
        "knowledge.remove": "Delete",
        "knowledge.close": "Close",
        "knowledge.new": "New document",
        "knowledge.text": "Text:",
        "knowledge.header": "Header",
        "knowledge.name": "Name:",
        "knowledge.tags": "Tags",
        "knowledge.tags_hint": "Comma-separated (optional):",
        "knowledge.empty": "empty fragment",
        "knowledge.delete": "Delete document",
        "knowledge.delete_question": "Delete {path} from the knowledge base?",
    },
}


def current_language() -> str:
    """Язык интерфейса: GIPERION_LANG, иначе ru."""

    value = os.environ.get("GIPERION_LANG", "").strip().lower()

    return value if value in LANGUAGES else DEFAULT_LANGUAGE


def tr(key: str, language: str | None = None, **values) -> str:
    """Строка на выбранном языке; неизвестный ключ возвращается как есть."""

    lang = language if language in LANGUAGES else current_language()
    table = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
    text = table.get(key) or TRANSLATIONS[DEFAULT_LANGUAGE].get(key) or key

    try:
        return text.format(**values)
    except (KeyError, IndexError):
        return text
