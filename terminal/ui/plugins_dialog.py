# Giperion/terminal/ui/plugins_dialog.py                               v001
# Экран установленных плагинов: разрешения, риск и отзыв.
# Последнее изменение: первый вариант — список и удаление.

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from terminal.core.agent import plugins
from terminal.core.agent.registry import reload_plugins
from terminal.ui.dialogs_base import SkinDialog, show_tool_window


class PluginsDialog(SkinDialog):
    """Показывает разрешения установленных плагинов."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Плагины",
            min_width=700,
            min_height=480,
        )
        self._build()
        self._reload()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Разрешения берутся из манифеста. Отзыв удаляет папку "
                "плагина из data/agent_tools.",
                self,
            )
        )

        self.list = QListWidget(self)
        self.list.currentItemChanged.connect(self._show)
        layout.addWidget(self.list, 1)

        self.detail = QPlainTextEdit(self)
        self.detail.setReadOnly(True)
        self.detail.setFixedHeight(120)
        layout.addWidget(self.detail)

        row = QHBoxLayout()
        revoke = QPushButton("Отозвать", self)
        revoke.clicked.connect(self._revoke)
        close = QPushButton("Закрыть", self)
        close.clicked.connect(self.close)
        row.addWidget(revoke)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)

    def _reload(self) -> None:
        self.list.clear()

        for item in plugins.list_installed():
            row = QListWidgetItem(
                f"{item['name']} · risk={item['risk']} · "
                + (", ".join(item["permissions"]) or "без разрешений")
            )
            row.setData(0x0100, item)
            self.list.addItem(row)

        if self.list.count():
            self.list.setCurrentRow(0)

    def _show(self, current, _previous=None) -> None:
        if current is None:
            self.detail.setPlainText("")
            return

        item = current.data(0x0100) or {}
        self.detail.setPlainText(
            f"{item.get('name')}\n"
            f"риск: {item.get('risk')}\n"
            f"разрешения: {', '.join(item.get('permissions') or []) or '—'}\n"
            f"папка: {item.get('folder')}\n\n"
            f"{item.get('description') or ''}"
        )

    def _revoke(self) -> None:
        current = self.list.currentItem()

        if current is None:
            return

        item = current.data(0x0100) or {}
        name = str(item.get("name") or "")

        answer = QMessageBox.question(
            self,
            "Отозвать плагин",
            f"Удалить плагин «{name}» и его разрешения?",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            plugins.revoke(name)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Не отозван", str(error))
            return

        reload_plugins()
        self._reload()


def show_plugins_dialog(parent) -> None:
    """Открывает экран плагинов."""

    dialog = PluginsDialog(parent)
    show_tool_window(parent, dialog, "agent-plugins")


def add_plugins_button(form, parent):
    """Добавляет кнопку «Плагины…» в форму настроек."""

    button = QPushButton("Плагины…", parent)
    button.setToolTip("Разрешения установленных плагинов и отзыв.")
    button.clicked.connect(lambda: show_plugins_dialog(parent))
    form.addRow("Разрешения", button)

    return button
