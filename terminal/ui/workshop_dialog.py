# Giperion/terminal/ui/workshop_dialog.py                            v002
# Окно «Мастерская»: терминал связи, плиты и кнопки инструментов.
# Последнее изменение: раскладка как у главного окна Гипериона.

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizeGrip,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from terminal.ui.dialogs_base import SkinDialog, show_tool_window

# Порядок важен: он же порядок кнопок в правой плите.
WORKSHOP_ACTIONS = (
    ("Агент", "agent"),
    ("Модель", "models"),
    ("Личности", "personalities"),
    ("Умения", "skills"),
    ("Журнал", "runs"),
)


class WorkshopDialog(SkinDialog):
    """Окно мастерской с кнопками свернуть, развернуть и закрыть."""

    def __init__(
        self,
        parent,
        title: str,
        min_width: int = 540,
        min_height: int = 420,
    ) -> None:
        super().__init__(parent, title, min_width, min_height)

        self.setSizeGripEnabled(False)
        self.size_grip = QSizeGrip(self)
        self.size_grip.setObjectName("workshopSizeGrip")
        self.size_grip.setFixedSize(18, 18)
        self.size_grip.raise_()

        layout = self.title_bar.layout()
        close_button = self.title_bar.findChild(
            QPushButton,
            "closeButton",
        )

        if layout is None or close_button is None:
            return

        position = layout.indexOf(close_button)

        self.minimize_button = self._title_button(
            "—",
            "Свернуть",
        )
        self.maximize_button = self._title_button(
            "▢",
            "Развернуть",
        )

        layout.insertWidget(position, self.minimize_button)
        layout.insertWidget(position + 1, self.maximize_button)

        self.minimize_button.clicked.connect(self.showMinimized)
        self.maximize_button.clicked.connect(self._toggle_maximize)

    def resizeEvent(self, event) -> None:
        """Держит размерный уголок в правом нижнем углу."""

        super().resizeEvent(event)

        if hasattr(self, "size_grip"):
            self.size_grip.move(
                max(0, self.width() - 20),
                max(0, self.height() - 20),
            )
            self.size_grip.raise_()

    def _title_button(
        self,
        text: str,
        tooltip: str,
    ) -> QPushButton:
        """Создаёт кнопку планки в стиле главного окна."""

        button = QPushButton(text, self.title_bar)
        button.setObjectName("titleButton")
        button.setToolTip(tooltip)
        button.setFixedSize(40, 30)
        button.setCursor(Qt.ArrowCursor)
        button.setFocusPolicy(Qt.NoFocus)

        return button

    def _toggle_maximize(self) -> None:
        """Разворачивает окно на экран и возвращает обратно."""

        if self.isMaximized():
            self.showNormal()

            geometry = getattr(self, "_normal_geometry", None)

            if geometry is not None:
                self.setGeometry(geometry)
                self._normal_geometry = None

            self.maximize_button.setText("▢")
            self.maximize_button.setToolTip("Развернуть")
        else:
            self._normal_geometry = self.geometry()
            self.showMaximized()
            self.maximize_button.setText("❐")
            self.maximize_button.setToolTip("Свернуть в окно")


def _panel(
    parent: QWidget,
    caption: str,
    object_name: str,
    *,
    min_width: int = 0,
    max_width: int = 0,
) -> QWidget:
    """Собирает плиту с подписью в стиле главного окна."""

    panel = QWidget(parent)
    panel.setObjectName(object_name)
    panel.setAttribute(Qt.WA_StyledBackground, True)

    if min_width:
        panel.setMinimumWidth(min_width)

    if max_width:
        panel.setMaximumWidth(max_width)

    layout = QVBoxLayout(panel)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    label = QLabel(caption, panel)
    label.setObjectName("panelCaption")
    label.setSizePolicy(
        QSizePolicy.Preferred,
        QSizePolicy.Fixed,
    )

    layout.addWidget(label)

    return panel


def _output_block(
    parent: QWidget,
    caption: str,
    object_name: str,
    widget_type,
    placeholder: str,
) -> tuple[QWidget, QWidget]:
    """Собирает окно вывода: подпись и сам терминал."""

    block = QWidget(parent)
    block.setObjectName("workshopOutput")

    layout = QVBoxLayout(block)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    label = QLabel(caption, block)
    label.setObjectName("workshopPaneCaption")

    view = widget_type(block)
    view.setObjectName(object_name)
    view.setReadOnly(True)
    view.setPlainText(placeholder)

    layout.addWidget(label)
    layout.addWidget(view, 1)

    return block, view


def _empty_plate(parent: QWidget) -> QWidget:
    """Пустая плита с текстурой, без содержимого."""

    plate = QWidget(parent)
    plate.setObjectName("paramsScreen")
    plate.setAttribute(Qt.WA_StyledBackground, True)
    plate.setSizePolicy(
        QSizePolicy.Expanding,
        QSizePolicy.Expanding,
    )

    return plate


def _picture_slot(parent: QWidget) -> QWidget:
    """Поле под будущую картинку модели."""

    slot = QFrame(parent)
    slot.setObjectName("workshopPictureSlot")
    slot.setMinimumHeight(220)

    layout = QVBoxLayout(slot)
    layout.setContentsMargins(10, 10, 10, 10)

    placeholder = QLabel("МЕСТО ДЛЯ ИЗОБРАЖЕНИЯ", slot)
    placeholder.setObjectName("workshopPlaceholder")
    placeholder.setAlignment(Qt.AlignCenter)
    placeholder.setWordWrap(True)

    layout.addWidget(placeholder, 1)

    return slot


def _build_left_column(
    dialog: QWidget,
) -> tuple[QWidget, QWidget]:
    """Левая колонка: образ модели и пустая плита параметров."""

    image_panel = _panel(
        dialog,
        "ОБРАЗ ГИПЕРИОНА",
        "avatarPanel",
        min_width=280,
        max_width=320,
    )
    image_panel.layout().addWidget(
        _picture_slot(image_panel),
        1,
    )

    details_panel = _panel(
        dialog,
        "ПАРАМЕТРЫ ИИ-ЯДРА",
        "personalityPanel",
        min_width=280,
        max_width=320,
    )
    details_panel.layout().addWidget(
        _empty_plate(details_panel),
        1,
    )

    return image_panel, details_panel


def _build_terminal(
    dialog: QWidget,
) -> tuple[QWidget, QWidget, QWidget, QWidget, QWidget]:
    """Центр: два равных окна вывода, журнал и строка ввода."""

    terminal = _panel(
        dialog,
        "ТЕРМИНАЛ СВЯЗИ",
        "chatPanel",
        min_width=560,
    )
    layout = terminal.layout()

    outputs = QGridLayout()
    outputs.setContentsMargins(0, 0, 0, 0)
    outputs.setHorizontalSpacing(6)
    outputs.setVerticalSpacing(6)

    answers_block, answers = _output_block(
        terminal,
        "ОТВЕТЫ МОДЕЛИ",
        "workshopAnswers",
        QTextBrowser,
        "Ответы модели появятся здесь.",
    )
    system_block, system = _output_block(
        terminal,
        "СИСТЕМНЫЕ КОМАНДЫ",
        "systemLog",
        QPlainTextEdit,
        "Системные сообщения появятся здесь.",
    )
    tools_block, tools = _output_block(
        terminal,
        "ЖУРНАЛ ИНСТРУМЕНТОВ",
        "agentTrace",
        QPlainTextEdit,
        "Журнал вызовов инструментов пока пуст.",
    )

    # Первые два окна равны по размеру; журнал занимает всю ширину ниже.
    outputs.addWidget(answers_block, 0, 0)
    outputs.addWidget(system_block, 0, 1)
    outputs.addWidget(tools_block, 1, 0, 1, 2)
    outputs.setColumnStretch(0, 1)
    outputs.setColumnStretch(1, 1)
    outputs.setRowStretch(0, 3)
    outputs.setRowStretch(1, 2)

    message_input = QPlainTextEdit(terminal)
    message_input.setObjectName("workshopInput")
    message_input.setPlaceholderText("Сообщение в мастерскую…")
    message_input.setFixedHeight(
        message_input.fontMetrics().lineSpacing() * 3 + 18
    )

    layout.addLayout(outputs, 1)
    layout.addWidget(message_input, 0)

    return terminal, answers, system, tools, message_input


def _build_actions_panel(
    dialog: QWidget,
    window,
) -> QWidget:
    """Правая верхняя плита: все кнопки мастерской."""

    actions_panel = _panel(
        dialog,
        "МАСТЕРСКАЯ",
        "chatsPanel",
        min_width=230,
        max_width=270,
    )
    layout = actions_panel.layout()
    actions = {
        "agent": window.open_agent_dialog,
        "models": window.open_models_dialog,
        "personalities": window.open_personalities_dialog,
        "skills": window.open_skills_dialog,
        "runs": window.open_agent_runs_dialog,
    }

    def launch(action) -> None:
        """Открывает инструмент после закрытия меню-кнопки."""

        QTimer.singleShot(0, action)

    for title, key in WORKSHOP_ACTIONS:
        button = QPushButton(title, actions_panel)
        button.setObjectName("workshopAction")
        button.setCursor(Qt.ArrowCursor)
        button.setMinimumHeight(38)
        button.clicked.connect(
            lambda _checked=False, action=actions[key]: launch(action)
        )
        layout.addWidget(button)

    layout.addStretch(1)

    return actions_panel


def _build_system_panel(dialog: QWidget) -> QWidget:
    """Правая нижняя плита: пока пустая текстура."""

    panel = _panel(
        dialog,
        "СИСТЕМА",
        "systemPanel",
        min_width=230,
        max_width=270,
    )
    panel.layout().addWidget(_empty_plate(panel), 1)

    return panel


def _build_workshop(dialog: QWidget, window) -> None:
    """Собирает сетку мастерской по образцу главного окна."""

    root = QGridLayout()
    root.setContentsMargins(0, 0, 0, 0)
    root.setHorizontalSpacing(8)
    root.setVerticalSpacing(8)

    image_panel, details_panel = _build_left_column(dialog)
    (
        terminal,
        answers,
        system,
        tools,
        message_input,
    ) = _build_terminal(dialog)
    actions_panel = _build_actions_panel(dialog, window)
    system_panel = _build_system_panel(dialog)

    root.addWidget(image_panel, 0, 0)
    root.addWidget(details_panel, 1, 0)
    root.addWidget(terminal, 0, 1, 2, 1)
    root.addWidget(actions_panel, 0, 2)
    root.addWidget(system_panel, 1, 2)
    root.setColumnStretch(0, 0)
    root.setColumnStretch(1, 1)
    root.setColumnStretch(2, 0)
    root.setRowStretch(0, 1)
    root.setRowStretch(1, 1)

    dialog.body_layout.addLayout(root, 1)

    # Публичные ссылки: следующие шаги смогут подключить живой вывод.
    dialog.terminal_answers = answers
    dialog.terminal_system = system
    dialog.terminal_tools = tools
    dialog.terminal_input = message_input


def show_workshop_dialog(parent, window) -> None:
    """Открывает «Мастерскую» как окно-станцию с терминалом и кнопками."""

    dialog = WorkshopDialog(
        parent,
        "Мастерская",
        min_width=1120,
        min_height=720,
    )
    dialog.body_layout.setContentsMargins(10, 8, 10, 10)
    dialog.body_layout.setSpacing(8)

    _build_workshop(dialog, window)

    show_tool_window(parent, dialog, "workshop")
