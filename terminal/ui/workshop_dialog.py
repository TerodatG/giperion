# Giperion/terminal/ui/workshop_dialog.py                            v001
# Окно «Мастерская»: сборка моделей, личностей и умений.
# Последнее изменение: первый вариант — четыре карточки-инструмента.

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from terminal.ui.add_model_dialog import show_add_model_dialog
from terminal.ui.dialogs_base import SkinDialog, show_tool_window


def _card(
    parent: QWidget,
    title: str,
    description: str,
    action_text: str,
    action,
) -> QFrame:
    """Собирает карточку мастерской: рамка, зелёный экран и кнопка."""

    plate = QFrame(parent)
    plate.setObjectName("paramsPlate")

    plate_layout = QVBoxLayout(plate)
    plate_layout.setContentsMargins(0, 0, 0, 0)
    plate_layout.setSpacing(0)

    screen = QWidget(plate)
    screen.setObjectName("paramsScreen")

    screen_layout = QVBoxLayout(screen)
    screen_layout.setContentsMargins(12, 10, 12, 10)
    screen_layout.setSpacing(6)

    caption = QLabel(title, screen)
    caption.setObjectName("paramsPlateTitle")

    hint = QLabel(description, screen)
    hint.setObjectName("paramsNote")
    hint.setWordWrap(True)

    button = QPushButton(action_text, screen)
    button.setObjectName("workshopAction")
    button.clicked.connect(action)

    screen_layout.addWidget(caption)
    screen_layout.addWidget(hint)
    screen_layout.addStretch(1)
    screen_layout.addWidget(button)

    plate_layout.addWidget(screen)

    return plate


def show_workshop_dialog(parent, window) -> None:
    """Открывает окно «Мастерская» с инструментами сборки."""

    dialog = SkinDialog(
        parent,
        "Мастерская",
        min_width=820,
        min_height=560,
    )

    title = QLabel("МАСТЕРСКАЯ", dialog)
    title.setObjectName("dialogTitle")

    subtitle = QLabel(
        "Сборка и настройка узлов Гипериона. Здесь собираются модели, "
        "личности и умения — через уже готовые окна.",
        dialog,
    )
    subtitle.setObjectName("dialogHint")
    subtitle.setWordWrap(True)

    def launch(action) -> None:
        """Открывает выбранный инструмент, не закрывая мастерскую."""

        QTimer.singleShot(0, action)

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(12)

    cards = (
        (
            "АГЕНТ",
            "Задача по проекту: поиск, чтение файлов и отчёт со ссылками.",
            "Открыть агента",
            lambda: launch(window.open_agent_dialog),
        ),
        (
            "МОДЕЛИ",
            "Каталог моделей, карточки, компаньоны и сенат.",
            "Открыть «Модель»",
            lambda: launch(window.open_models_dialog),
        ),
        (
            "ЛИЧНОСТИ",
            "Личностные матрицы и выбор характера Гипериона.",
            "Открыть личности",
            lambda: launch(window.open_personalities_dialog),
        ),
        (
            "УМЕНИЯ",
            "Что умеет ядро и что умеют подключённые модели.",
            "Открыть умения",
            lambda: launch(window.open_skills_dialog),
        ),
        (
            "СВОЯ МОДЕЛЬ",
            "Добавить собственный канал и описать его возможности.",
            "Добавить модель",
            lambda: launch(
                lambda: show_add_model_dialog(parent)
            ),
        ),
    )

    for index, (card_title, text, button_text, action) in enumerate(cards):
        grid.addWidget(
            _card(
                dialog,
                card_title,
                text,
                button_text,
                action,
            ),
            index // 2,
            index % 2,
        )

    buttons = QDialogButtonBox(QDialogButtonBox.Close, dialog)
    buttons.button(QDialogButtonBox.Close).setText("Закрыть")
    buttons.rejected.connect(dialog.reject)

    dialog.body_layout.addWidget(title)
    dialog.body_layout.addWidget(subtitle)
    dialog.body_layout.addLayout(grid, 1)
    dialog.body_layout.addWidget(buttons)

    show_tool_window(parent, dialog, "workshop")
