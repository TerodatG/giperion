# Giperion/terminal/ui/knowledge_dialog.py                             v001
# Окно базы знаний: поиск, цитаты, добавление и удаление.
# Последнее изменение: первый вариант — semantic-поиск и knowledge/.

from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from terminal.core.agent import knowledge
from terminal.ui.dialogs_base import SkinDialog, show_tool_window
from terminal.ui.i18n import tr
from tools import knowledge_add


class KnowledgeDialog(SkinDialog):
    """Поиск по knowledge/ и управление документами."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            tr("knowledge.title"),
            min_width=760,
            min_height=520,
        )
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        hint = QLabel(
            tr("knowledge.hint"),
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        row = QHBoxLayout()
        self.query = QLineEdit(self)
        self.query.setPlaceholderText(tr("knowledge.query"))
        self.query.returnPressed.connect(self._search)
        search = QPushButton(tr("knowledge.search"), self)
        search.clicked.connect(self._search)
        row.addWidget(self.query, 1)
        row.addWidget(search)
        layout.addLayout(row)

        self.results = QListWidget(self)
        self.results.currentItemChanged.connect(self._preview)
        layout.addWidget(self.results, 1)

        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setFixedHeight(160)
        layout.addWidget(self.preview)

        buttons = QHBoxLayout()
        add = QPushButton(tr("knowledge.add"), self)
        add.clicked.connect(self._add)
        remove = QPushButton(tr("knowledge.remove"), self)
        remove.clicked.connect(self._remove)
        close = QPushButton(tr("knowledge.close"), self)
        close.clicked.connect(self.close)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _search(self) -> None:
        """Ищет по смыслу и заполняет список."""

        self.results.clear()
        self.preview.setPlainText("")

        for item in knowledge.search(self.query.text(), limit=12):
            label = (
                f"{item['path']}:{item['line']} · "
                f"{item['title']} · {item['score']:.2f}"
            )
            row = QListWidgetItem(label)
            row.setData(0x0100, item)
            self.results.addItem(row)

    def _preview(self, current, _previous=None) -> None:
        """Показывает фрагмент выбранной цитаты."""

        if current is None:
            return

        item = current.data(0x0100) or {}
        self.preview.setPlainText(
            f"{item.get('path')}:{item.get('line')}\n\n"
            f"{item.get('snippet') or tr('knowledge.empty')}"
        )

    def _add(self) -> None:
        """Добавляет заметку в knowledge/."""

        text, ok = QInputDialog.getMultiLineText(
            self,
            tr("knowledge.new"),
            tr("knowledge.text"),
        )

        if not ok or not text.strip():
            return

        title, ok = QInputDialog.getText(
            self,
            tr("knowledge.header"),
            tr("knowledge.name"),
        )

        if not ok:
            return

        tags, _ok = QInputDialog.getText(
            self,
            tr("knowledge.tags"),
            tr("knowledge.tags_hint"),
        )
        cleaned = [
            item.strip()
            for item in tags.split(",")
            if item.strip()
        ]

        try:
            path = knowledge_add.add_text(
                text,
                title.strip() or "note",
                tags=cleaned,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Не добавлено", str(error))

            return

        self.preview.setPlainText("Добавлено: " + path.name)
        self._search()

    def _remove(self) -> None:
        """Удаляет выбранный документ после подтверждения."""

        current = self.results.currentItem()

        if current is None:
            return

        item = current.data(0x0100) or {}
        path = str(item.get("path") or "")

        if not path:
            return

        answer = QMessageBox.question(
            self,
            tr("knowledge.delete"),
            tr("knowledge.delete_question", path=path),
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            knowledge.remove(path)
        except ValueError as error:
            QMessageBox.warning(self, "Не удалено", str(error))

            return

        self._search()


def show_knowledge_dialog(parent) -> None:
    """Открывает окно базы знаний."""

    dialog = KnowledgeDialog(parent)
    show_tool_window(parent, dialog, "agent-knowledge")


def add_knowledge_button(form, parent):
    """Добавляет кнопку «База знаний…» в форму настроек."""

    button = QPushButton("База знаний…", parent)
    button.setToolTip(
        "Поиск по knowledge/, цитаты, добавление и удаление."
    )
    button.clicked.connect(lambda: show_knowledge_dialog(parent))
    form.addRow("Знания", button)

    return button
