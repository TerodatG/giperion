# Giperion/terminal/ui/pets/card.py                                    v001
# Карточка дрона: кличка, характер, успехи и статус.
# Последнее изменение: вынесено из pets_dialog.

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from terminal.ui.rating_bars import fill_rating_bars


class PetCard(QWidget):
    """Правая колонка окна «Дроны»."""

    rename_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setObjectName("paramsPlate")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.screen = QWidget(self)
        self.screen.setObjectName("paramsScreen")
        self.screen.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self.screen)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.name_label = QLabel(self)
        self.name_label.setObjectName("modelName")
        self.name_label.setWordWrap(True)

        self.nickname_label = QLabel(self)
        self.nickname_label.setObjectName("modelNickname")
        self.nickname_label.setWordWrap(True)

        self.rename_button = QPushButton("✎ Переименовать", self)
        self.rename_button.setObjectName("aiParamsButton")
        self.rename_button.setCursor(Qt.ArrowCursor)
        self.rename_button.setFocusPolicy(Qt.NoFocus)
        self.rename_button.setToolTip("Изменить кличку дрона")
        self.rename_button.clicked.connect(self.rename_requested.emit)

        nickname_row = QHBoxLayout()
        nickname_row.setContentsMargins(0, 0, 0, 0)
        nickname_row.setSpacing(8)
        nickname_row.addWidget(self.nickname_label, 1)
        nickname_row.addWidget(self.rename_button, 0, Qt.AlignRight)

        identity = QHBoxLayout()
        identity.setSpacing(12)

        self.avatar_label = QLabel(self)
        self.avatar_label.setObjectName("modelAvatar")
        self.avatar_label.setFixedSize(96, 96)
        self.avatar_label.setAlignment(Qt.AlignCenter)

        self.traits_widget = QWidget(self)
        self.traits_layout = QVBoxLayout(self.traits_widget)
        self.traits_layout.setContentsMargins(0, 0, 0, 0)
        self.traits_layout.setSpacing(3)

        identity.addWidget(self.avatar_label)
        identity.addWidget(self.traits_widget, 1)

        self.description_label = QLabel(self)
        self.description_label.setObjectName("modelDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.training_caption = QLabel("УСПЕХИ ОБУЧЕНИЯ", self)
        self.training_caption.setObjectName("infoCaption")

        training_screen = QWidget(self)
        training_screen.setObjectName("petTrainingScreen")

        training_layout = QVBoxLayout(training_screen)
        training_layout.setContentsMargins(10, 8, 10, 8)
        training_layout.setSpacing(4)

        self.training_level = QLabel(training_screen)
        self.training_level.setObjectName("petTrainingLine")

        self.training_conversations = QLabel(training_screen)
        self.training_conversations.setObjectName("petTrainingLine")

        self.training_learned = QLabel(training_screen)
        self.training_learned.setObjectName("petTrainingLine")

        self.training_experience = QLabel(training_screen)
        self.training_experience.setObjectName("petTrainingLine")

        self.training_bar = QProgressBar(training_screen)
        self.training_bar.setObjectName("petTrainingBar")
        self.training_bar.setRange(0, 100)
        self.training_bar.setTextVisible(False)
        self.training_bar.setFixedHeight(10)

        training_layout.addWidget(self.training_level)
        training_layout.addWidget(self.training_conversations)
        training_layout.addWidget(self.training_learned)
        training_layout.addWidget(self.training_experience)
        training_layout.addWidget(self.training_bar)

        self.traits_caption = QLabel("ХАРАКТЕР · ОЦЕНКА 0–5", self)
        self.traits_caption.setObjectName("infoCaption")

        self.speech_caption = QLabel("МАНЕРА ОБЩЕНИЯ", self)
        self.speech_caption.setObjectName("infoCaption")

        self.speech_label = QLabel(self)
        self.speech_label.setObjectName("modelDescription")
        self.speech_label.setWordWrap(True)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("modelStatus")
        self.status_label.setWordWrap(True)

        layout.addWidget(self.name_label)
        layout.addLayout(nickname_row)
        layout.addWidget(self.traits_caption)
        layout.addLayout(identity)
        layout.addWidget(self.description_label)
        layout.addWidget(self.training_caption)
        layout.addWidget(training_screen)
        layout.addWidget(self.speech_caption)
        layout.addWidget(self.speech_label)
        layout.addStretch(1)
        layout.addWidget(self.status_label)
        outer.addWidget(self.screen)

    def show_pet(self, pet: dict | None, active: str = "") -> None:
        """Заполняет карточку выбранным дроном или пустым состоянием."""

        self.rename_button.setEnabled(pet is not None)

        if pet is None:
            self.name_label.setText("Выбери дрона")
            self.nickname_label.setText("")
            self.description_label.setText("")
            self.speech_label.setText("")
            self.status_label.setText("")
            self.avatar_label.setText("")
            self.training_level.setText("")
            self.training_conversations.setText("")
            self.training_learned.setText("")
            self.training_experience.setText("")
            self.training_bar.setValue(0)
            self._fill_traits(None)

            return

        progress = pet.get("progress") or {}
        level = int(progress.get("level", 1) or 1)
        experience = int(progress.get("experience", 0) or 0)
        conversations = int(progress.get("conversations", 0) or 0)
        learned = int(progress.get("learned_phrases", 0) or 0)

        nickname = pet.get("nickname") or ""

        self.name_label.setText(pet["name"])
        self.nickname_label.setText(
            f"КЛИЧКА: {nickname}" if nickname else "КЛИЧКА: не задана"
        )
        self.nickname_label.setStyleSheet(
            "" if nickname else "color: #6f7d72;"
        )
        self.description_label.setText(
            pet.get("description") or "Описание пока не заполнено."
        )
        self.speech_label.setText(pet.get("speech") or "")
        self.avatar_label.setText(pet.get("symbol") or "🐾")

        self.training_level.setText(f"Уровень: {level}")
        self.training_conversations.setText(
            f"Разговоров: {conversations}"
        )
        self.training_learned.setText(f"Выучено фраз: {learned}")
        self.training_experience.setText(
            f"Опыт: {experience} · до следующего уровня "
            f"{100 - experience % 100}"
        )
        self.training_bar.setValue(experience % 100)

        self._fill_traits(pet)

        self.status_label.setText(
            "Статус: закреплён за терминалом."
            if pet["id"] == active
            else "Статус: свободен."
        )

    def _fill_traits(self, pet: dict | None) -> None:
        """Перерисовывает шкалы характера."""

        ratings = (pet.get("traits") or {}) if pet is not None else {}

        fill_rating_bars(
            self.traits_layout,
            self.traits_widget,
            ratings,
            name_width=120,
        )
