# Giperion/tests/test_agent_knowledge.py                                v001
# База знаний: разбор цитат и безопасное удаление.

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from terminal.core.agent import knowledge
from terminal.core.agent.protocol import ToolResult


def test_search_parses_citations(monkeypatch) -> None:
    """Цитаты получают путь, строку и фрагмент."""

    text = (
        "Найдено 1 фрагмент\n"
        "- knowledge/a.md:12 [section] Решение (0.87)\n"
        "  текст решения\n"
        "  вторая строка"
    )
    monkeypatch.setattr(
        "terminal.core.agent.semantic.find_relevant",
        lambda *args, **kwargs: ToolResult(True, text),
    )

    found = knowledge.search("решение")

    assert len(found) == 1
    assert found[0]["path"] == "knowledge/a.md"
    assert found[0]["line"] == 12
    assert found[0]["title"] == "Решение"
    assert found[0]["score"] == 0.87
    assert "текст решения" in found[0]["snippet"]


def test_remove_only_inside_knowledge(tmp_path) -> None:
    """Удаление вне knowledge/ запрещено."""

    folder = tmp_path / "knowledge"
    folder.mkdir()
    target = folder / "a.md"
    target.write_text("текст", encoding="utf-8")
    outside = tmp_path / "a.md"
    outside.write_text("не трогать", encoding="utf-8")

    assert knowledge.remove("knowledge/a.md", root=tmp_path)
    assert not target.exists()

    with pytest.raises(ValueError):
        knowledge.remove("../a.md", root=tmp_path)
    assert outside.exists()


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def test_dialog_shows_results(qapp, monkeypatch) -> None:
    """Окно заполняет список и показывает фрагмент."""

    from terminal.ui.knowledge_dialog import KnowledgeDialog

    monkeypatch.setattr(
        knowledge,
        "search",
        lambda *args, **kwargs: [
            {
                "path": "knowledge/a.md",
                "line": 3,
                "kind": "section",
                "title": "Решение",
                "score": 0.9,
                "snippet": "фрагмент",
            }
        ],
    )

    dialog = KnowledgeDialog(None)

    try:
        dialog._search()

        assert dialog.results.count() == 1
        dialog.results.setCurrentRow(0)
        assert "фрагмент" in dialog.preview.toPlainText()
    finally:
        dialog.close()
