# Giperion/app/core/pending_state.py                              v001
# Состояние диалога: ожидающее действие и ожидающее уточнение.
# Последнее изменение: состояние можно переключать между чатами окна.

from dataclasses import dataclass


@dataclass
class DialogState:
    """Незавершённые шаги одного диалога.

    pending_action — системная операция, ждущая «подтверждаю».
    pending_clarification — фраза, которую Гиперион предложил уточнить.
    """

    pending_action: dict[str, str] | None = None
    pending_clarification: str | None = None


def new_state() -> DialogState:
    """Создаёт чистое состояние для нового чата."""

    return DialogState()


_current_state = new_state()


def get_state() -> DialogState:
    """Возвращает состояние активного диалога."""

    return _current_state


def set_state(state: DialogState) -> None:
    """Делает указанное состояние активным."""

    global _current_state

    _current_state = state


# --- Ожидающее системное действие ---


def set_pending_action(
    action: str,
    archive_id: str | None = None,
    category: str | None = None,
    phrase: str | None = None,
    response: str | None = None,
) -> None:
    """Сохраняет одно ожидающее подтверждения действие."""

    record = {
        "action": action,
    }

    if archive_id is not None:
        record["archive_id"] = archive_id

    if category is not None:
        record["category"] = category

    if phrase is not None:
        record["phrase"] = phrase

    if response is not None:
        record["response"] = response

    _current_state.pending_action = record


def get_pending_action() -> dict[str, str] | None:
    """Возвращает ожидающее действие или None."""

    return _current_state.pending_action


def has_pending_action() -> bool:
    """Проверяет, ждёт ли система подтверждения."""

    return _current_state.pending_action is not None


def clear_pending_action() -> None:
    """Удаляет ожидающее подтверждения действие."""

    _current_state.pending_action = None


# --- Ожидающее уточнение фразы ---


def set_pending_clarification(phrase: str) -> None:
    """Запоминает фразу, которую Гиперион предложил уточнить."""

    _current_state.pending_clarification = phrase


def get_pending_clarification() -> str | None:
    """Возвращает фразу, ожидающую подтверждения, или None."""

    return _current_state.pending_clarification


def clear_pending_clarification() -> None:
    """Удаляет ожидающее уточнение фразы."""

    _current_state.pending_clarification = None


def clear_state() -> None:
    """Сбрасывает незавершённые шаги активного диалога."""

    _current_state.pending_action = None
    _current_state.pending_clarification = None
