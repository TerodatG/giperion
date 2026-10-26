# Giperion/terminal/ui/memory_dialog.py                                v001
# Просмотр и редактирование памяти проекта (data/agent_memory.md).
# Последнее изменение: первый вариант — текст, сохранение и очистка.

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from terminal.core.agent import memory
from terminal.ui.dialogs_base import SkinDialog, show_tool_window


class MemoryDialog(SkinDialog):
    """Редактор заметок, которые попадают в системный промпт."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Память проекта",
            min_width=640,
            min_height=420,
        )

        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Заметки из data/agent_memory.md. Последние 4 000 символов "
            "попадают в системный промпт следующих задач. Инструмент "
            "remember дописывает их сам.",
            self,
        )
        hint.setWordWrap(True)
        hint.setObjectName("dialogHint")
        layout.addWidget(hint)

        self.editor = QPlainTextEdit(self)
        self.editor.setPlainText(memory.load_notes(limit=memory.MAX_CHARS))
        layout.addWidget(self.editor, 1)

        self.status = QLabel("", self)
        self.status.setObjectName("dialogHint")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        save = QPushButton("Сохранить", self)
        save.clicked.connect(self._save)
        clear = QPushButton("Очистить", self)
        clear.clicked.connect(self._clear)
        close = QPushButton("Закрыть", self)
        close.clicked.connect(self.close)
        row.addWidget(save)
        row.addWidget(clear)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)

    def _save(self) -> None:
        """Записывает текст в память, обрезая по лимиту."""

        text = self.editor.toPlainText().strip()

        if len(text) > memory.MAX_CHARS:
            text = text[-memory.MAX_CHARS:]

        memory.MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        memory.MEMORY_FILE.write_text(
            text + ("\n" if text else ""),
            encoding="utf-8",
        )
        self.status.setText(
            f"Сохранено символов: {len(text)}."
        )

    def _clear(self) -> None:
        """Удаляет память после подтверждения."""

        answer = QMessageBox.question(
            self,
            "Очистить память",
            "Удалить все заметки? Следующие задачи их не увидят.",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        memory.clear()
        self.editor.setPlainText("")
        self.status.setText("Память очищена.")


def show_memory_dialog(parent) -> None:
    """Открывает редактор памяти немодальным окном."""

    dialog = MemoryDialog(parent)
    show_tool_window(parent, dialog, "agent-memory")
