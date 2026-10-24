# Giperion/app/storage/json_store.py                              v002
# Единое чтение и атомарная запись JSON-файлов проекта.
# Последнее изменение: добавлено чтение JSON-объекта с проверкой типа.

import json
import os
import tempfile
from pathlib import Path


def read_json(
    path: Path | str,
    default: object = None,
) -> object:
    """Читает JSON-файл. При отсутствии или ошибке возвращает default."""

    file_path = Path(path)

    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def read_json_object(
    path: Path | str,
) -> dict:
    """Читает JSON-объект; неверный формат превращается в пустой словарь."""

    document = read_json(path, {})

    return document if isinstance(document, dict) else {}


def write_json(
    path: Path | str,
    data: object,
    *,
    indent: int = 2,
    trailing_newline: bool = False,
) -> None:
    """Записывает JSON атомарно: временный файл, затем замена.

    Если запись прервётся, старый файл останется целым. Каталог
    создаётся автоматически. Кириллица сохраняется как есть.
    """

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    descriptor = -1
    temporary_path: Path | None = None

    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)

        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
            newline="\n",
        ) as file:
            descriptor = -1

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=indent,
            )

            if trailing_newline:
                file.write("\n")

            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_path, file_path)
        temporary_path = None
    finally:
        if descriptor != -1:
            os.close(descriptor)

        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
