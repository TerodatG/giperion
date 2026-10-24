# Giperion/app/ui/input_mixin.py                                    v001
# Ввод с Enter и русские контекстные меню чата и поля ввода.
# Последнее изменение: методы вынесены из GiperionWindow как отдельный слой.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu

from terminal.ui.window_events import ChatEventFilter


class InputMixin:
    """Методы окна для клавиатуры и контекстных меню."""

    def _input_key_press(self, event) -> bool:
        """Отправляет сообщение по Enter без Shift."""

        if (
            event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and not event.modifiers() & Qt.ShiftModifier
        ):
            # Пока идёт ответ, Enter не должен добавлять пустые строки.
            if not self.answering:
                self.send_message()

            return True

        return False

    # --- Меню правой кнопки мыши ---

    def _build_context_menus(self) -> None:
        """Русские меню правой кнопки и Enter в поле ввода."""

        self.chat_filter = ChatEventFilter(self)
        self.chat.installEventFilter(self.chat_filter)
        self.input.installEventFilter(self.chat_filter)
        self.window.personalityPanel.installEventFilter(
            self.chat_filter
        )

    def _chat_context_menu(self, event) -> None:
        """Меню истории чата: копировать и выделить всё."""

        self._chat_menu().exec(event.globalPos())

    def _chat_menu(self) -> QMenu:
        """Собирает меню истории чата."""

        menu = QMenu(self.chat)

        copy_action = menu.addAction("Копировать")
        copy_action.setEnabled(
            self.chat.textCursor().hasSelection()
        )
        copy_action.triggered.connect(
            lambda: self.chat.copy()
        )

        select_action = menu.addAction("Выделить всё")
        select_action.triggered.connect(
            lambda: self.chat.selectAll()
        )

        return menu

    def _input_context_menu(self, event) -> None:
        """Меню поля ввода: вырезать, копировать, вставить, очистить."""

        self._input_menu().exec(event.globalPos())

    def _input_menu(self) -> QMenu:
        """Собирает меню поля ввода."""

        menu = QMenu(self.input)

        cut_action = menu.addAction("Вырезать")
        cut_action.triggered.connect(lambda: self.input.cut())

        copy_action = menu.addAction("Копировать")
        copy_action.triggered.connect(lambda: self.input.copy())

        paste_action = menu.addAction("Вставить")
        paste_action.triggered.connect(lambda: self.input.paste())

        menu.addSeparator()

        select_action = menu.addAction("Выделить всё")
        select_action.triggered.connect(
            lambda: self.input.selectAll()
        )

        clear_action = menu.addAction("Очистить")
        clear_action.triggered.connect(lambda: self.input.clear())

        return menu
