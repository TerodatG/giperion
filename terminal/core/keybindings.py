# Giperion/terminal/core/keybindings.py                              v001
# Назначение клавиш: список действий, значения по умолчанию и хранение.
# Последнее изменение: первый вариант — действия окна и проверка конфликтов.

from dataclasses import dataclass

from terminal.core.window_settings import (
    load_window_settings,
    save_window_settings,
)


@dataclass(frozen=True)
class KeyAction:
    """Действие, которому можно назначить клавиши."""

    id: str
    title: str
    hint: str
    default: str
    scope: str = "window"


# Порядок важен: так действия идут в настройках.
ACTIONS = (
    KeyAction(
        "send",
        "Отправить сообщение",
        "в поле ввода; Shift+Enter — новая строка",
        "Return",
        "input",
    ),
    KeyAction("new_chat", "Новый чат", "", "Ctrl+N"),
    KeyAction("focus_input", "Фокус в поле ввода", "", "Ctrl+L"),
    KeyAction("clear_chat", "Очистить чат", "", "Ctrl+Shift+Backspace"),
    KeyAction("settings", "Настройки", "", "Ctrl+,"),
    KeyAction("models", "Окно «Модель»", "", "Ctrl+M"),
    KeyAction("drones", "Окно «Дроны»", "", "Ctrl+D"),
    KeyAction("agent", "Окно «Агент»", "", "Ctrl+G"),
    KeyAction("performance", "Производительность", "", "F5"),
    KeyAction("update", "Обновление", "", "F6"),
)

ACTION_IDS = tuple(action.id for action in ACTIONS)

DEFAULT_BINDINGS = {
    action.id: action.default for action in ACTIONS
}


def clean_binding(value: object) -> str:
    """Проверяет строку клавиш: пустая или слишком длинная — пусто."""

    if not isinstance(value, str):
        return ""

    text = " ".join(value.split())

    if len(text) > 40:
        return ""

    return text


def normalize_binding(value: object) -> str:
    """Приводит клавиши к виду для сравнения на конфликты."""

    return "".join(clean_binding(value).split()).lower()


def load_bindings() -> dict:
    """Читает назначения из настроек, дополняя значениями по умолчанию."""

    settings = load_window_settings()
    raw = settings.get("keys")
    bindings = dict(DEFAULT_BINDINGS)

    if not isinstance(raw, dict):
        return bindings

    for action in ACTIONS:
        if action.id in raw:
            bindings[action.id] = clean_binding(raw[action.id])

    return bindings


def save_bindings(bindings: dict) -> dict:
    """Сохраняет назначения и возвращает очищенный словарь."""

    clean = {
        action.id: clean_binding(
            bindings.get(action.id, DEFAULT_BINDINGS[action.id])
        )
        for action in ACTIONS
    }

    settings = load_window_settings()
    settings["keys"] = clean
    save_window_settings(settings)

    return clean


def reset_bindings() -> dict:
    """Возвращает назначения по умолчанию (без записи на диск)."""

    return dict(DEFAULT_BINDINGS)


def find_conflicts(bindings: dict) -> list[tuple[str, list[str]]]:
    """Ищет действия с одинаковыми клавишами.

    Возвращает пары «клавиши — список действий», где клавиши повторяются.
    """

    used: dict[str, list[str]] = {}

    for action in ACTIONS:
        key = normalize_binding(bindings.get(action.id, ""))

        if not key:
            continue

        used.setdefault(key, []).append(action.id)

    return [
        (key, ids)
        for key, ids in used.items()
        if len(ids) > 1
    ]


def action_title(action_id: str) -> str:
    """Название действия по идентификатору."""

    for action in ACTIONS:
        if action.id == action_id:
            return action.title

    return action_id
