# Giperion/app/ui/dialogs_base.py                                   v001
# Базовые окна в металлической шкуре: планка, каркас и подтверждения.
# Последнее изменение: вынесены из gui.py без изменения поведения.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from terminal.ui.window_help import show_window_help


class DialogTitleBar(QWidget):
    """Планка заголовка дополнительных окон в стиле «шкуры»."""

    def __init__(self, parent, title_text: str) -> None:
        super().__init__(parent)

        self.setObjectName("dialogTitleBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(46)

        self._drag_position = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 2, 8, 2)
        layout.setSpacing(8)

        emblem = QLabel("◈", self)
        emblem.setObjectName("titleBadge")

        title = QLabel(title_text.upper(), self)
        title.setObjectName("dialogTitleText")

        layout.addWidget(emblem)
        layout.addWidget(title)
        layout.addStretch(1)

        help_button = QPushButton("?", self)
        help_button.setObjectName("titleButton")
        help_button.setToolTip("Справка по окну")
        help_button.setFixedSize(40, 30)
        help_button.setCursor(Qt.ArrowCursor)
        help_button.setFocusPolicy(Qt.NoFocus)
        help_button.clicked.connect(self._request_help)

        close_button = QPushButton("✕", self)
        close_button.setObjectName("closeButton")
        close_button.setToolTip("Закрыть окно")
        close_button.setFixedSize(40, 30)
        close_button.setCursor(Qt.ArrowCursor)
        close_button.setFocusPolicy(Qt.NoFocus)
        close_button.clicked.connect(self.window().close)

        layout.addWidget(help_button)
        layout.addWidget(close_button)

        for element in (emblem, title):
            element.setAttribute(
                Qt.WA_TransparentForMouseEvents,
                True,
            )

    def _request_help(self) -> None:
        """Передаёт запрос справки окну-владельцу."""

        request = getattr(self.window(), "request_help", None)

        if callable(request):
            request()

    def mousePressEvent(self, event) -> None:
        """Запоминает точку, за которую тянут окно."""

        if event.button() == Qt.LeftButton:
            self._drag_position = (
                event.globalPosition().toPoint()
                - self.window().frameGeometry().topLeft()
            )
            event.accept()

            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Переносит окно вместе с мышью."""

        if (
            self._drag_position is not None
            and event.buttons() & Qt.LeftButton
        ):
            self.window().move(
                event.globalPosition().toPoint()
                - self._drag_position
            )
            event.accept()

            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Завершает перенос окна."""

        self._drag_position = None
        super().mouseReleaseEvent(event)


class SkinDialog(QDialog):
    """Базовое окно с металлической планкой вместо системной рамки."""

    def __init__(
        self,
        parent,
        title: str,
        min_width: int = 540,
        min_height: int = 420,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setObjectName("skinDialog")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumSize(min_width, min_height)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = DialogTitleBar(self, title)
        outer.addWidget(self.title_bar)

        self.body = QWidget(self)
        self.body.setObjectName("skinDialogBody")
        self.body.setAttribute(Qt.WA_StyledBackground, True)

        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(16, 14, 16, 12)
        self.body_layout.setSpacing(8)

        outer.addWidget(self.body, 1)

    def request_help(self) -> None:
        """Открывает раздел справки по этому окну."""

        show_window_help(self, self.windowTitle())


class ChatRenameDialog(SkinDialog):
    """Окно переименования открытого чата в стиле «шкуры»."""

    def __init__(self, parent, current_name: str) -> None:
        super().__init__(
            parent,
            "Переименовать чат",
            min_width=480,
            min_height=210,
        )

        title = QLabel("ИМЯ ЧАТА", self)
        title.setObjectName("dialogTitle")

        hint = QLabel(
            "Новое имя появится в списке «Открытые чаты».",
            self,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        self.name_input = QLineEdit(current_name, self)
        self.name_input.setMaxLength(64)
        self.name_input.selectAll()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            self,
        )
        buttons.button(QDialogButtonBox.Ok).setText("Сохранить")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")

        def update_ok() -> None:
            """Не разрешает сохранить пустое имя."""

            buttons.button(QDialogButtonBox.Ok).setEnabled(
                bool(self.name_input.text().strip())
            )

        self.name_input.textChanged.connect(update_ok)
        self.name_input.returnPressed.connect(self.accept)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(hint)
        self.body_layout.addWidget(self.name_input)
        self.body_layout.addStretch(1)
        self.body_layout.addWidget(buttons)

        update_ok()
        self.name_input.setFocus()

    def chat_name(self) -> str:
        """Возвращает очищенное имя чата."""

        return self.name_input.text().strip()


class ConfirmDialog(SkinDialog):
    """Небольшое окно подтверждения опасного действия."""

    def __init__(
        self,
        parent,
        title: str,
        text: str,
        confirm_text: str = "Удалить",
    ) -> None:
        super().__init__(
            parent,
            title,
            min_width=480,
            min_height=220,
        )

        heading = QLabel(title.upper(), self)
        heading.setObjectName("dialogTitle")

        message = QLabel(text, self)
        message.setObjectName("dialogHint")
        message.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            self,
        )
        buttons.button(QDialogButtonBox.Ok).setText(confirm_text)
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.body_layout.addWidget(heading)
        self.body_layout.addWidget(message, 1)
        self.body_layout.addWidget(buttons)


def show_tool_window(
    parent,
    dialog: QDialog,
    key: str = "",
) -> None:
    """Показывает инструмент без модальности и держит его, пока он открыт.

    Окна терминала не должны блокировать друг друга: можно открыть
    «Модель», «Личность» и «Настройки» одновременно. Ссылка хранится
    у родителя, иначе Python соберёт окно сразу после показа.
    """

    dialog.setModal(False)
    dialog.setWindowModality(Qt.NonModal)
    dialog.setAttribute(Qt.WA_DeleteOnClose, True)

    owner = parent if parent is not None else dialog
    windows = getattr(owner, "_tool_windows", None)

    if not isinstance(windows, dict):
        windows = {}
        owner._tool_windows = windows

    if key:
        existing = windows.get(key)

        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            dialog.deleteLater()

            return

        windows[key] = dialog
        dialog.destroyed.connect(
            lambda *_: windows.pop(key, None)
        )

    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
