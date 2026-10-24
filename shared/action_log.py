# Giperion/app/core/action_log.py                                 v001
# Журнал действий Giperion с датой, временем и номером записи.
# Последнее изменение: создан инструмент записи и просмотра действий.

from datetime import datetime
from pathlib import Path

from config import ACTIONS_LOG_FILE

LOG_FILE: Path = ACTIONS_LOG_FILE


def get_last_record_number() -> int:
    """Возвращает номер последней записи журнала."""

    if not LOG_FILE.exists():
        return 0

    last_number = 0

    with LOG_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            parts = line.split(" | ", maxsplit=2)

            if len(parts) != 3 or not parts[0].isdigit():
                raise ValueError(
                    "Журнал действий повреждён: неверный формат записи."
                )

            record_number = int(parts[0])

            if record_number != last_number + 1:
                raise ValueError(
                    "Журнал действий повреждён: нарушена нумерация."
                )

            last_number = record_number

    return last_number


def add_action(description: str) -> int:
    """Добавляет короткое описание действия и возвращает номер записи."""

    clean_description = " ".join(
        description.split()
    ).replace("|", "/")

    if not clean_description:
        raise ValueError(
            "Описание действия не может быть пустым."
        )

    LOG_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record_number = get_last_record_number() + 1
    created_at = datetime.now().strftime(
        "%d.%m.%Y %H:%M:%S"
    )

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(
            f"{record_number:06d} | "
            f"{created_at} | "
            f"{clean_description}\n"
        )

    return record_number


def get_recent_actions(limit: int = 10) -> list[str]:
    """Возвращает последние записи журнала."""

    if limit < 1:
        return []

    if not LOG_FILE.exists():
        return []

    with LOG_FILE.open("r", encoding="utf-8") as file:
        lines = [
            line.rstrip("\n")
            for line in file
            if line.strip()
        ]

    return lines[-limit:]