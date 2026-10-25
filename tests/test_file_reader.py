# Giperion/tests/test_file_reader.py                                v001
# Проверки чтения текстовых файлов для окна чата.
# Последнее изменение: UTF-8, cp1251, двоичные файлы и обрезка.

import pytest

from terminal.skills.file_reader import (
    MAX_TEXT_CHARS,
    FileReadError,
    read_text_file,
)


def test_reads_utf8_file(tmp_path) -> None:
    """Обычный UTF-8 файл читается и сохраняет переводы строк."""

    path = tmp_path / "note.txt"
    path.write_text(
        "Привет, Гиперион!\nВторая строка.",
        encoding="utf-8",
    )

    data = read_text_file(path)

    assert data["name"] == "note.txt"
    assert data["text"] == "Привет, Гиперион!\nВторая строка."
    assert data["truncated"] is False
    assert data["encoding"] in ("utf-8-sig", "utf-8")


def test_reads_cp1251_file(tmp_path) -> None:
    """Старый файл Windows в cp1251 не превращается в мусор."""

    path = tmp_path / "old.txt"
    path.write_bytes("Привет из старого файла".encode("cp1251"))

    data = read_text_file(path)

    assert data["text"] == "Привет из старого файла"
    assert data["encoding"] == "cp1251"


def test_rejects_binary_file(tmp_path) -> None:
    """Файл с нулевым байтом не считается текстом."""

    path = tmp_path / "image.bin"
    path.write_bytes(b"\x89PNG\x00\x01\x02")

    with pytest.raises(FileReadError):
        read_text_file(path)


def test_large_text_is_truncated(tmp_path) -> None:
    """Очень длинный текст обрезается до безопасного предела."""

    path = tmp_path / "long.txt"
    path.write_text(
        "а" * (MAX_TEXT_CHARS + 50),
        encoding="utf-8",
    )

    data = read_text_file(path)

    assert data["truncated"] is True
    assert data["full_length"] == MAX_TEXT_CHARS + 50
    assert len(data["text"]) == MAX_TEXT_CHARS


def test_missing_file_raises(tmp_path) -> None:
    """Отсутствующий файл даёт понятную ошибку."""

    with pytest.raises(FileReadError):
        read_text_file(tmp_path / "missing.txt")
