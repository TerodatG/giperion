# Giperion/terminal/ui/help_dialog.py                                v001
# Отдельное окно «Справка»: навыки, вопросы и системные команды.
# Последнее изменение: раздел вынесен из настроек.

from PySide6.QtWidgets import (
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from terminal.core.help_handler import get_help_sections
from terminal.ui.dialog_text import build_help_html
from terminal.ui.dialogs_base import SkinDialog, show_tool_window


class HelpDialog(SkinDialog):
    """Окно справки по возможностям и командам Гипериона."""

    def __init__(self, parent=None) -> None:
        super().__init__(
            parent,
            "Справка",
            min_width=760,
            min_height=600,
        )

        page = QWidget(self.body)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("СПРАВКА", page)
        title.setObjectName("dialogTitle")

        hint = QLabel(
            "Навыки ядра, обычные вопросы и системные команды. "
            "Системная команда вводится в чат целиком, вместе со "
            "словом «Гиперион».",
            page,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        view = QTextBrowser(page)
        view.setObjectName("helpView")
        view.setOpenLinks(False)
        view.setHtml(build_help_html(get_help_sections()))

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(view, 1)

        self.body_layout.addWidget(page, 1)


def show_help_dialog(parent) -> None:
    """Открывает окно «Справка» или поднимает уже открытое."""

    dialog = HelpDialog(parent)

    show_tool_window(parent, dialog, "help")
