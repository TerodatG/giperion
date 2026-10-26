# Giperion/app/ui/input_mixin.py                                    v002
# Ввод по назначенной клавише и русские контекстные меню.
# Последнее изменение: отправка по настраиваемой клавише.

from PySide6.QtWidgets import QMenu

from terminal.ui.window_events import ChatEventFilter


class InputMixin:
    """Методы окна для клавиатуры и контекстных меню."""

    def _input_key_press(self, event) -> bool:
        """Отправляет сообщение по назначенной клавише.

        По умолчанию это Enter; Shift+Enter остаётся переводом строки,
        потому что модификатор меняет сочетание.
        """

        if self.binding_matches("send", event):
            # Пока идёт ответ, клавиша не должна добавлять пустые строки.
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
