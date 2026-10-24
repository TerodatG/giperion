# Giperion/app/core/chat_context.py                                v001
# Выжимка диалога открытого чата для передачи новой модели.
# Последнее изменение: первый вариант — файл контекста без системных сообщений.

import os
from datetime import datetime
from pathlib import Path

from config import DATA_DIR

CHAT_CONTEXTS_DIR = DATA_DIR / "chat_contexts"

# Сколько символов последней истории передаём модели.
MAX_CONTEXT_CHARS = 12_000


def new_context_id(sequence: int) -> str:
    """Создаёт уникальный идентификатор контекста для нового чата."""

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"chat_{sequence:03d}_{stamp}"


def context_file(
    context_id: str,
    directory: Path | None = None,
) -> Path:
    """Возвращает путь к файлу выжимки."""

    root = Path(directory or CHAT_CONTEXTS_DIR)

    return root / f"{context_id}.txt"


def build_chat_summary(
    chat_log: list,
    max_chars: int = MAX_CONTEXT_CHARS,
) -> str:
    """Собирает реплики пользователя и моделей без системных сообщений."""

    lines = []

    for entry in chat_log:
        if not entry:
            continue

        role = entry[0]

        if role == "user" and len(entry) >= 2:
            text = str(entry[1]).strip()

            if text:
                lines.append(f"Пользователь: {text}")
        elif role == "bot" and len(entry) >= 2:
            text = str(entry[1]).strip()

            if not text:
                continue

            speaker = "Модель"

            if len(entry) >= 5 and entry[4]:
                speaker = str(entry[4])

            lines.append(f"{speaker}: {text}")

    if not lines:
        return ""

    summary = "\n\n".join(lines)

    if len(summary) > max_chars:
        summary = (
            "…(начало диалога сокращено)\n\n"
            + summary[-max_chars:]
        )

    return summary


def write_chat_context(
    context_id: str,
    chat_name: str,
    chat_log: list,
    directory: Path | None = None,
) -> Path:
    """Записывает выжимку чата в текстовый файл."""

    path = context_file(context_id, directory)
    path.parent.mkdir(parents=True, exist_ok=True)

    summary = build_chat_summary(chat_log)
    header = (
        f"# Контекст чата «{chat_name}»\n"
        f"# Обновлено: {datetime.now():%d.%m.%Y %H:%M:%S}\n"
        "# Только реплики пользователя и моделей, без системных сообщений.\n"
    )

    if summary:
        body = f"{header}\n{summary}\n"
    else:
        body = f"{header}\n(диалог пока пуст)\n"

    temporary = path.with_suffix(".tmp")

    try:
        temporary.write_text(body, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

    return path


def read_chat_context(
    context_id: str,
    directory: Path | None = None,
) -> str:
    """Читает выжимку чата; при ошибке возвращает пустую строку."""

    path = context_file(context_id, directory)

    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def remove_chat_context(
    context_id: str,
    directory: Path | None = None,
) -> None:
    """Удаляет файл выжимки вместе с закрытым чатом."""

    context_file(context_id, directory).unlink(missing_ok=True)
