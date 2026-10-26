# Giperion/terminal/ui/settings_keys.py                              v001
# Раздел «Назначение клавиш»: строки действий и перехват нажатий.
# Последнее изменение: первый вариант — редактор и применение.

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from terminal.core.keybindings import (
    ACTIONS,
    DEFAULT_BINDINGS,
    action_title,
    find_conflicts,
    load_bindings,
)

# Клавиши-модификаторы: их нажатие не считается назначением.
_MODIFIER_KEYS = (
    Qt.Key_Shift,
    Qt.Key_Control,
    Qt.Key_Alt,
    Qt.Key_Meta,
    Qt.Key_AltGr,
    Qt.Key_unknown,
)


class KeysPage(QWidget):
    """Страница назначения клавиш."""

    def __init__(
        self,
        parent,
        bindings: dict | None = None,
        on_apply=None,
    ) -> None:
        super().__init__(parent)

        self.setFocusPolicy(Qt.StrongFocus)

        self.on_apply = on_apply
        self.bindings = dict(bindings or load_bindings())
        self._capturing = ""
        self.key_buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("НАЗНАЧЕНИЕ КЛАВИШ", self)
        title.setObjectName("dialogTitle")

        hint = QLabel(
            "Клавиши работают, когда окно активно. Нажми на комбинацию, "
            "чтобы назначить новую: Esc — отмена, Backspace — очистить.",
            self,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        scroll = QScrollArea(self)
        scroll.setObjectName("systemScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        screen = QWidget()
        screen.setObjectName("keysScreen")

        grid = QGridLayout(screen)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(0, 1)

        for row, action in enumerate(ACTIONS):
            names = QVBoxLayout()
            names.setContentsMargins(0, 0, 0, 0)
            names.setSpacing(1)

            name_label = QLabel(action.title, screen)
            name_label.setObjectName("keyActionName")
            name_label.setWordWrap(True)

            names.addWidget(name_label)

            if action.hint:
                hint_label = QLabel(action.hint, screen)
                hint_label.setObjectName("keyActionHint")
                hint_label.setWordWrap(True)

                names.addWidget(hint_label)

            key_button = QPushButton("", screen)
            key_button.setObjectName("keyBindingButton")
            key_button.setCursor(Qt.PointingHandCursor)
            key_button.setMinimumWidth(170)
            key_button.setFocusPolicy(Qt.NoFocus)
            key_button.clicked.connect(
                lambda checked=False, action_id=action.id: (
                    self._start_capture(action_id)
                )
            )

            reset_button = QPushButton("↺", screen)
            reset_button.setObjectName("keyResetButton")
            reset_button.setCursor(Qt.ArrowCursor)
            reset_button.setFocusPolicy(Qt.NoFocus)
            reset_button.setFixedSize(32, 30)
            reset_button.setToolTip("Вернуть по умолчанию")
            reset_button.clicked.connect(
                lambda checked=False, action_id=action.id: (
                    self._reset(action_id)
                )
            )

            grid.addLayout(names, row, 0)
            grid.addWidget(key_button, row, 1)
            grid.addWidget(reset_button, row, 2)

            self.key_buttons[action.id] = key_button

        scroll.setWidget(screen)

        self.description = QLabel("", self)
        self.description.setObjectName("dialogHint")
        self.description.setWordWrap(True)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("settingsStatus")
        self.status_label.setWordWrap(True)

        self.reset_button = QPushButton("Сбросить всё", self)
        self.reset_button.setCursor(Qt.ArrowCursor)
        self.reset_button.clicked.connect(self._reset_all)

        self.apply_button = QPushButton("Применить", self)
        self.apply_button.setCursor(Qt.ArrowCursor)
        self.apply_button.setMinimumWidth(140)
        self.apply_button.clicked.connect(self._apply)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        buttons.addWidget(self.reset_button)
        buttons.addWidget(self.apply_button)
        buttons.addStretch(1)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)

        self._refresh_buttons()
        self.status_label.setText(
            "Нажми на клавиши действия, чтобы назначить новые."
        )

    # --- Отрисовка ---

    def _refresh_buttons(self) -> None:
        """Пишет текущие комбинации на кнопках."""

        for action_id, button in self.key_buttons.items():
            binding = self.bindings.get(action_id, "")

            if action_id == self._capturing:
                button.setText("Нажми комбинацию…")
            else:
                button.setText(binding or "не задано")

    # --- Перехват клавиш ---

    def _start_capture(self, action_id: str) -> None:
        """Начинает ждать новую комбинацию для действия."""

        self._capturing = action_id
        self._refresh_buttons()

        self.status_label.setText(
            "Нажми новую комбинацию. Esc — отмена, Backspace — очистить."
        )

        self.setFocus(Qt.OtherFocusReason)

    def _cancel_capture(self) -> None:
        """Отменяет перехват."""

        self._capturing = ""
        self._refresh_buttons()
        self.status_label.setText("Назначение отменено.")

    def keyPressEvent(self, event) -> None:
        """Принимает следующую комбинацию для выбранного действия."""

        if not self._capturing:
            super().keyPressEvent(event)

            return

        key = event.key()

        if key == Qt.Key_Escape:
            self._cancel_capture()

            return

        if key in (Qt.Key_Backspace, Qt.Key_Delete):
            self.bindings[self._capturing] = ""
            self._capturing = ""
            self._refresh_buttons()
            self.status_label.setText(
                "Клавиши сняты. Не забудь нажать «Применить»."
            )

            return

        if key in _MODIFIER_KEYS:
            return

        sequence = QKeySequence(
            event.keyCombination()
        ).toString(QKeySequence.PortableText)

        if not sequence:
            return

        action_id = self._capturing

        self.bindings[action_id] = sequence
        self._capturing = ""
        self._refresh_buttons()
        self.status_label.setText(
            f"«{action_title(action_id)}»: {sequence}. "
            "Не забудь нажать «Применить»."
        )

    # --- Действия ---

    def _reset(self, action_id: str) -> None:
        """Возвращает одно действие к значению по умолчанию."""

        self.bindings[action_id] = DEFAULT_BINDINGS.get(action_id, "")
        self._refresh_buttons()
        self.status_label.setText(
            "Действие вернулось к значению по умолчанию. "
            "Не забудь нажать «Применить»."
        )

    def _reset_all(self) -> None:
        """Сбрасывает все назначения."""

        self.bindings = dict(DEFAULT_BINDINGS)
        self._capturing = ""
        self._refresh_buttons()
        self.status_label.setText(
            "Все клавиши вернулись к значениям по умолчанию. "
            "Не забудь нажать «Применить»."
        )

    def _apply(self) -> None:
        """Проверяет конфликты и применяет назначения."""

        conflicts = find_conflicts(self.bindings)

        if conflicts:
            parts = []

            for key, action_ids in conflicts:
                names = ", ".join(
                    f"«{action_title(action_id)}»"
                    for action_id in action_ids
                )
                parts.append(f"{key}: {names}")

            self.status_label.setText(
                "Клавиши повторяются — " + "; ".join(parts) + "."
            )

            return

        if self.on_apply is not None:
            self.bindings = dict(self.on_apply(self.bindings))
            self._refresh_buttons()

        self.status_label.setText("Назначения клавиш применены.")
