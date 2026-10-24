# Giperion/app/ui/window_events.py                                   v001
# Фильтры событий окна и поля ввода.
# Последнее изменение: вынесены из gui.py без изменения поведения.

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QCursor


class WindowCursorFilter(QObject):
    """Курсор у краёв окна и подтверждение закрытия."""

    def __init__(self, owner) -> None:
        """Запоминает окно-владельца."""

        super().__init__(owner.window)

        self.owner = owner
        self.shape = Qt.ArrowCursor

    def eventFilter(self, watched, event) -> bool:
        """Обновляет курсор и перехватывает закрытие окна."""

        kind = event.type()

        if kind == QEvent.MouseMove:
            self._update()
        elif kind == QEvent.Close and watched is self.owner.window:
            if self.owner._confirm_window_close():
                return False

            event.ignore()

            return True

        return False

    def _update(self) -> None:
        """Подбирает курсор под положение мыши."""

        window = self.owner.window

        if not window.isVisible():
            return

        position = window.mapFromGlobal(QCursor.pos())

        if window.isMaximized() or not window.rect().contains(position):
            shape = Qt.ArrowCursor
        else:
            shape = self.owner._edge_cursor(
                self.owner._window_edges(position)
            )

        if shape == self.shape:
            return

        self.shape = shape
        window.setCursor(shape)


class ChatEventFilter(QObject):
    """Русские меню правой кнопки и Enter в поле ввода."""

    def __init__(self, owner) -> None:
        """Запоминает владельца окна."""

        super().__init__(owner.window)

        self.owner = owner

    def eventFilter(self, watched, event) -> bool:
        """Подменяет меню правой кнопки и перехватывает Enter."""

        kind = event.type()

        if kind == QEvent.Resize:
            if watched is self.owner.input:
                self.owner._position_attachment_button()
            elif watched is self.owner.window.personalityPanel:
                self.owner._position_personality_backdrop()

            return False

        if kind == QEvent.ContextMenu:
            if watched is self.owner.chat:
                self.owner._chat_context_menu(event)

                return True

            if watched is self.owner.input:
                self.owner._input_context_menu(event)

                return True

        if kind == QEvent.KeyPress and watched is self.owner.input:
            return self.owner._input_key_press(event)

        return False
