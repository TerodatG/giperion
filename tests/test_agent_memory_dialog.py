# Giperion/tests/test_agent_memory_dialog.py                           v001
# Окно памяти: сохранение и очистка.

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from terminal.core.agent import memory


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def _dialog(tmp_path, monkeypatch):
    from terminal.ui.memory_dialog import MemoryDialog

    monkeypatch.setattr(
        memory,
        "MEMORY_FILE",
        tmp_path / "agent_memory.md",
    )

    return MemoryDialog(None)


def test_memory_dialog_saves(tmp_path, monkeypatch, qapp) -> None:
    """Текст из окна попадает в файл памяти."""

    dialog = _dialog(tmp_path, monkeypatch)

    try:
        dialog.editor.setPlainText("- 2026-10-27: тесты перед коммитом")
        dialog._save()

        assert "тесты перед коммитом" in memory.load_notes()
        assert "Сохранено" in dialog.status.text()
    finally:
        dialog.close()


def test_memory_dialog_clears(tmp_path, monkeypatch, qapp) -> None:
    """Очистка удаляет файл после подтверждения."""

    from PySide6.QtWidgets import QMessageBox

    dialog = _dialog(tmp_path, monkeypatch)

    try:
        memory.add_note("временная")
        dialog.editor.setPlainText(memory.load_notes())

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
        )

        dialog._clear()

        assert memory.load_notes() == ""
        assert dialog.editor.toPlainText() == ""
    finally:
        dialog.close()
