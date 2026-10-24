# Giperion/app/ui/tab_strip.py                                     v001
# Полоса закладок без промежутков: равные кнопки на всю ширину.
# Последнее изменение: общий виджет для панели ядра и окна «Умения».

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QPushButton,
    QWidget,
)


class TabStrip(QWidget):
    """Ряд закладок-кнопок, связанный с индексом страницы."""

    tab_selected = Signal(int)

    def __init__(
        self,
        parent,
        titles: tuple[str, ...],
    ) -> None:
        super().__init__(parent)

        self.setObjectName("screenTabStrip")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: list[QPushButton] = []

        for index, title in enumerate(titles):
            button = QPushButton(title, self)
            button.setObjectName("screenTabButton")
            button.setCheckable(True)
            button.setCursor(Qt.ArrowCursor)
            button.setFocusPolicy(Qt.NoFocus)
            button.setMinimumHeight(36)

            self.group.addButton(button, index)
            layout.addWidget(button)
            self.buttons.append(button)

        self.buttons[0].setChecked(True)
        self.group.idClicked.connect(self.tab_selected)

    def set_current_index(self, index: int) -> None:
        """Подсвечивает закладку, соответствующую странице."""

        if 0 <= index < len(self.buttons):
            self.buttons[index].setChecked(True)
