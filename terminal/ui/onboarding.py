# Giperion/terminal/ui/onboarding.py                                   v001
# Онбординг первого запуска: три шага и «больше не показывать».
# Последнее изменение: первый вариант — модальное окно.

from PySide6.QtWidgets import (
    QCheckBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from terminal.core.agent import onboarding
from terminal.ui.dialogs_base import SkinDialog


class OnboardingDialog(SkinDialog):
    """Короткая инструкция для первого запуска агента."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Добро пожаловать в Giperion",
            min_width=560,
            min_height=360,
        )

        layout = QVBoxLayout(self)
        title = QLabel("Терминал готов к работе", self)
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        text = QLabel(
            "1. Опиши задачу в поле «Задача» и выбери модель.\n"
            "2. Агент читает проект и показывает каждый шаг; записи "
            "проходят только через подтверждение с диффом.\n"
            "3. «План…» показывает чек-лист, «Трейс…» — полный журнал, "
            "«С шага…» повторяет задачу иначе.\n\n"
            "Память проекта и база знаний — в «Провайдере».",
            self,
        )
        text.setWordWrap(True)
        layout.addWidget(text, 1)

        self.hide_check = QCheckBox(
            "Больше не показывать",
            self,
        )
        self.hide_check.setChecked(True)
        layout.addWidget(self.hide_check)

        button = QPushButton("Начать", self)
        button.clicked.connect(self.accept)
        layout.addWidget(button)


def maybe_show_onboarding(parent) -> None:
    """Показывает онбординг один раз, если он ещё не пройден."""

    if parent is None or onboarding.done():
        return

    dialog = OnboardingDialog(parent)
    dialog.exec()

    if dialog.hide_check.isChecked():
        onboarding.set_done(True)
