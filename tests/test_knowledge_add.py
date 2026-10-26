# Giperion/tests/test_knowledge_add.py                                 v001
# Импорт документов в knowledge/.

import pytest

from tools import knowledge_add


@pytest.fixture(autouse=True)
def _folder(tmp_path, monkeypatch):
    monkeypatch.setattr(
        knowledge_add,
        "KNOWLEDGE_DIR",
        tmp_path / "knowledge",
    )


def test_add_text_creates_markdown() -> None:
    """Текст сохраняется в knowledge/ с датой и слагом."""

    path = knowledge_add.add_text(
        "Redis не используем: только SQLite.",
        title="Решение по хранилищу",
    )

    assert path.exists()
    assert path.parent.name == "knowledge"
    assert "SQLite" in path.read_text(encoding="utf-8")
    assert path.name.endswith("решение-по-хранилищу.md")


def test_add_file_copies_text(tmp_path) -> None:
    """Текстовый файл копируется, расширение сохраняется."""

    source = tmp_path / "notes.md"
    source.write_text("# Заметка\n\nтекст", encoding="utf-8")

    path = knowledge_add.add_file(source)

    assert path.exists()
    assert "текст" in path.read_text(encoding="utf-8")


def test_rejects_empty_and_big() -> None:
    """Пустой и слишком большой текст не добавляются."""

    with pytest.raises(ValueError):
        knowledge_add.add_text("   ")

    with pytest.raises(ValueError):
        knowledge_add.add_text("х" * (knowledge_add.MAX_BYTES + 1))


def test_rejects_binary_suffix(tmp_path) -> None:
    """Двоичные файлы не копируются."""

    source = tmp_path / "image.png"
    source.write_bytes(b"\x89PNG")

    with pytest.raises(ValueError):
        knowledge_add.add_file(source)


def test_names_do_not_collide() -> None:
    """Два документа с одинаковым именем получают разные файлы."""

    first = knowledge_add.add_text("раз", title="Заметка")
    second = knowledge_add.add_text("два", title="Заметка")

    assert first != second
