# GiperionModel/giperion_model/_shared/json_store.py                  v003
# Единое чтение и атомарная запись JSON-файлов проекта.
# Последнее изменение: блокировки на путь и update_json для гонок.

import hashlib
import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

# Блокировки живут в памяти процесса и в отдельной папке временных файлов,
# чтобы один и тот же JSON не писали одновременно два потока или процесса.
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_OS_LOCK_DIR = Path(tempfile.gettempdir()) / "giperion-json-locks"


@contextmanager
def path_guard(path: Path | str):
    """Сериализует доступ к одному пути: внутри процесса и между процессами."""

    key = str(Path(path).resolve()).casefold()

    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(key, threading.RLock())

    with lock:
        with _os_guard(key):
            yield


@contextmanager
def _os_guard(key: str):
    """Межпроцессная блокировка через отдельный файл в TEMP.

    На Windows используется msvcrt, на остальных системах — fcntl.
    Если временную папку создать нельзя, остаётся только блокировка
    процесса: данные не должны падать из-за самой блокировки.
    """

    try:
        _OS_LOCK_DIR.mkdir(parents=True, exist_ok=True)
        lock_path = _OS_LOCK_DIR / (
            hashlib.sha256(key.encode("utf-8")).hexdigest() + ".lock"
        )
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_RDWR,
            0o600,
        )
    except OSError:
        yield

        return

    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")

        os.lseek(descriptor, 0, os.SEEK_SET)
        _lock_descriptor(descriptor)

        try:
            yield
        finally:
            _unlock_descriptor(descriptor)
    finally:
        os.close(descriptor)


def _lock_descriptor(descriptor: int) -> None:
    """Берёт блокировку на первый байт файла."""

    if os.name == "nt":
        import msvcrt

        deadline = time.monotonic() + 10.0

        while True:
            try:
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)

                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise

                time.sleep(0.05)

    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_EX)


def _unlock_descriptor(descriptor: int) -> None:
    """Снимает блокировку с первого байта файла."""

    if os.name == "nt":
        import msvcrt

        os.lseek(descriptor, 0, os.SEEK_SET)
        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)

        return

    import fcntl

    fcntl.flock(descriptor, fcntl.LOCK_UN)


def _read_json_unlocked(
    path: Path | str,
    default: object = None,
) -> object:
    """Читает JSON без взятия блокировки."""

    file_path = Path(path)

    try:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def read_json(
    path: Path | str,
    default: object = None,
) -> object:
    """Читает JSON-файл. При отсутствии или ошибке возвращает default."""

    with path_guard(path):
        return _read_json_unlocked(path, default)


def read_json_object(
    path: Path | str,
) -> dict:
    """Читает JSON-объект; неверный формат превращается в пустой словарь."""

    document = read_json(path, {})

    return document if isinstance(document, dict) else {}


def _write_json_unlocked(
    path: Path | str,
    data: object,
    *,
    indent: int = 2,
    trailing_newline: bool = False,
) -> None:
    """Пишет JSON атомарно; вызывающий уже держит блокировку пути."""

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

        _replace_with_retry(temporary_path, file_path)
        temporary_path = None
    finally:
        if descriptor != -1:
            os.close(descriptor)

        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _replace_with_retry(source: Path, target: Path) -> None:
    """Заменяет файл, переживая короткие блокировки Windows."""

    for attempt in range(5):
        try:
            os.replace(source, target)

            return
        except PermissionError:
            if attempt == 4:
                raise

            time.sleep(0.05 * (attempt + 1))


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

    with path_guard(path):
        _write_json_unlocked(
            path,
            data,
            indent=indent,
            trailing_newline=trailing_newline,
        )


def update_json(
    path: Path | str,
    mutator,
    *,
    default: object = None,
    indent: int = 2,
    trailing_newline: bool = False,
) -> object:
    """Меняет JSON под блокировкой: чтение и запись — одна операция.

    mutator получает прочитанное значение и возвращает новое. Если
    вернуть None, будет записано изменённое значение на месте.
    """

    with path_guard(path):
        document = _read_json_unlocked(path, default)
        updated = mutator(document)

        if updated is None:
            updated = document

        _write_json_unlocked(
            path,
            updated,
            indent=indent,
            trailing_newline=trailing_newline,
        )

        return updated
