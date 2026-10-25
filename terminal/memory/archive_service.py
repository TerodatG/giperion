# Giperion/app/memory/archive_service.py                          v005
# Создание, просмотр, восстановление и удаление архивов памяти Giperion.
# Последнее изменение: счётчик и описания архивов пишутся атомарно.

import re
import shutil
from datetime import datetime
from pathlib import Path

from config import (
    ARCHIVE_DIR,
    CONVERSATIONS_FILE,
    UNKNOWN_MESSAGES_FILE,
    USER_PROFILE_FILE,
)
from shared.storage.json_store import read_json, write_json

ARCHIVE_ID_PATTERN = re.compile(r"^\d{5}$")
ARCHIVE_INFO_FILE_NAME = "archive_info.json"
ARCHIVE_COUNTER_FILE_NAME = "archive_counter.json"

MEMORY_FILES = [
    USER_PROFILE_FILE,
    CONVERSATIONS_FILE,
    UNKNOWN_MESSAGES_FILE,
]


def get_archive_path(archive_id: str) -> Path | None:
    """Возвращает путь к архиву только для пятизначного номера."""

    if not ARCHIVE_ID_PATTERN.fullmatch(archive_id):
        return None

    return ARCHIVE_DIR / archive_id


def get_last_issued_archive_number() -> int:
    """Читает последний выданный номер архива из отдельного файла."""

    counter_path = ARCHIVE_DIR / ARCHIVE_COUNTER_FILE_NAME

    if not counter_path.exists():
        return 0

    counter_data = read_json(counter_path, None)

    if not isinstance(counter_data, dict):
        raise ValueError(
            "Счётчик архивов повреждён. Новый архив не создан."
        )

    last_number = counter_data.get("last_archive_number")

    if (
        isinstance(last_number, bool)
        or not isinstance(last_number, int)
        or last_number < 0
        or last_number > 99999
    ):
        raise ValueError(
            "Счётчик архивов повреждён. Новый архив не создан."
        )

    return last_number


def get_existing_max_archive_number() -> int:
    """Находит наибольший номер среди существующих папок архивов."""

    if not ARCHIVE_DIR.exists():
        return 0

    numbers = [
        int(path.name)
        for path in ARCHIVE_DIR.iterdir()
        if path.is_dir()
        and ARCHIVE_ID_PATTERN.fullmatch(path.name)
    ]

    return max(numbers, default=0)


def get_next_archive_id() -> str:
    """Возвращает номер больше сохранённого счётчика и существующих архивов."""

    last_issued_number = get_last_issued_archive_number()
    existing_max_number = get_existing_max_archive_number()

    next_number = max(
        last_issued_number,
        existing_max_number,
    ) + 1

    if next_number > 99999:
        raise ValueError(
            "Достигнут предел пятизначных номеров архивов."
        )

    return f"{next_number:05d}"


def save_last_issued_archive_number(archive_number: int) -> None:
    """Сохраняет счётчик атомарно, не теряя прежний файл при сбое."""

    counter_path = ARCHIVE_DIR / ARCHIVE_COUNTER_FILE_NAME

    write_json(
        counter_path,
        {"last_archive_number": archive_number},
    )


def create_archive() -> dict[str, str]:
    """Создаёт снимок памяти с новым, ранее не выданным номером."""

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    archive_id = get_next_archive_id()

    # Номер резервируется до создания архива: при ошибке допустим пропуск,
    # но повторно выдать тот же номер нельзя.
    save_last_issued_archive_number(int(archive_id))

    archive_path = ARCHIVE_DIR / archive_id
    archive_path.mkdir()

    try:
        for memory_file in MEMORY_FILES:
            destination = archive_path / memory_file.name

            if memory_file.exists():
                shutil.copy2(memory_file, destination)
            elif memory_file == USER_PROFILE_FILE:
                destination.write_text(
                    '{\n  "name": null\n}',
                    encoding="utf-8",
                )
            else:
                destination.write_text(
                    "[]",
                    encoding="utf-8",
                )

        created_at = datetime.now().isoformat(
            timespec="seconds"
        )

        archive_info = {
            "archive_id": archive_id,
            "created_at": created_at,
        }

        write_json(
            archive_path / ARCHIVE_INFO_FILE_NAME,
            archive_info,
        )

    except Exception:
        shutil.rmtree(archive_path)
        raise

    return archive_info


def get_archive_info(archive_id: str) -> dict[str, str] | None:
    """Возвращает сведения о существующем архиве."""

    archive_path = get_archive_path(archive_id)

    if archive_path is None or not archive_path.is_dir():
        return None

    info_path = archive_path / ARCHIVE_INFO_FILE_NAME

    if not info_path.exists():
        return None

    archive_info = read_json(info_path, None)

    if not isinstance(archive_info, dict):
        return None

    if (
        archive_info.get("archive_id") != archive_id
        or not isinstance(
            archive_info.get("created_at"),
            str,
        )
    ):
        return None

    return archive_info


def get_archives() -> list[dict[str, str]]:
    """Возвращает архивы от большего номера к меньшему."""

    if not ARCHIVE_DIR.exists():
        return []

    archives = []

    for archive_path in ARCHIVE_DIR.iterdir():
        if not archive_path.is_dir():
            continue

        archive_info = get_archive_info(archive_path.name)

        if archive_info:
            archives.append(archive_info)

    return sorted(
        archives,
        key=lambda archive: archive["archive_id"],
        reverse=True,
    )


def get_archive_files(archive_id: str) -> list[str] | None:
    """Возвращает имена файлов выбранного архива."""

    archive_path = get_archive_path(archive_id)

    if archive_path is None or not archive_path.is_dir():
        return None

    return sorted(
        file_path.name
        for file_path in archive_path.iterdir()
        if file_path.is_file()
    )


def format_archive_datetime(iso_datetime: str) -> str:
    """Преобразует дату в формат ДД.ММ.ГГГГ ЧЧ:ММ."""

    try:
        archive_datetime = datetime.fromisoformat(
            iso_datetime
        )
    except ValueError:
        return "дата неизвестна"

    return archive_datetime.strftime("%d.%m.%Y %H:%M")


def restore_archive(archive_id: str) -> bool:
    """Восстанавливает три файла памяти из выбранного архива."""

    archive_path = get_archive_path(archive_id)

    if archive_path is None or not archive_path.is_dir():
        return False

    for memory_file in MEMORY_FILES:
        if not (archive_path / memory_file.name).is_file():
            return False

    for memory_file in MEMORY_FILES:
        archive_file = archive_path / memory_file.name
        memory_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        shutil.copy2(archive_file, memory_file)

    return True


def delete_archive(archive_id: str) -> bool:
    """Удаляет архив, не меняя счётчик выданных номеров."""

    archive_path = get_archive_path(archive_id)

    if archive_path is None or not archive_path.is_dir():
        return False

    shutil.rmtree(archive_path)

    return True