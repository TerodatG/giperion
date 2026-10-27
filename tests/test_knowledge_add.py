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

def test_tags_are_added_to_header() -> None:
    """Теги и дата попадают в шапку документа."""

    path = knowledge_add.add_text(
        "Текст решения",
        title="Хранилище",
        tags=["sqlite", "#архитектура"],
    )

    text = path.read_text(encoding="utf-8")

    assert "# Хранилище" in text
    assert "Теги: sqlite, архитектура" in text
    assert "Добавлено:" in text
    assert "Текст решения" in text


def test_duplicate_returns_existing_path() -> None:
    """Одинаковый текст не создаёт второй документ."""

    first = knowledge_add.add_text("Одно решение", title="Раз")
    second = knowledge_add.add_text("Одно решение", title="Два")

    assert first == second
    assert len(list(first.parent.glob("*.md"))) == 1


def test_html_import_strips_markup(tmp_path) -> None:
    """HTML импортируется без тегов и скриптов."""

    source = tmp_path / "page.html"
    source.write_text(
        "<html><body><h1>Заголовок</h1>"
        "<script>alert(1)</script><p>Текст &amp; ещё</p></body></html>",
        encoding="utf-8",
    )

    path = knowledge_add.add_file(source)
    text = path.read_text(encoding="utf-8")

    assert "Заголовок" in text
    assert "Текст & ещё" in text
    assert "alert" not in text
    assert "<p>" not in text


def test_docx_import_reads_paragraphs(tmp_path) -> None:
    """DOCX читается через word/document.xml."""

    import zipfile

    source = tmp_path / "doc.docx"

    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main"><w:body>'
                "<w:p><w:r><w:t>Первый</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>Второй</w:t></w:r></w:p>"
                "</w:body></w:document>"
            ),
        )

    path = knowledge_add.add_file(source)
    text = path.read_text(encoding="utf-8")

    assert "Первый" in text
    assert "Второй" in text


def test_pdf_without_library_has_hint(tmp_path, monkeypatch) -> None:
    """Без pypdf ошибка объясняет, что установить."""

    import sys

    source = tmp_path / "doc.pdf"
    source.write_bytes(b"%PDF-1.4")
    monkeypatch.setitem(sys.modules, "pypdf", None)

    with pytest.raises(ValueError, match="pypdf"):
        knowledge_add.add_file(source)
