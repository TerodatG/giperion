# Giperion/app/ui/chat_list_widgets.py                              v001
# Список открытых чатов и его кнопка «...» в строке.
# Последнее изменение: вынесено из gui.py без изменения поведения.

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QListWidget,
    QStyle,
    QStyledItemDelegate,
)


class ChatItemDelegate(QStyledItemDelegate):
    """Рисует три точки действий в правой части строки чата."""

    DOT_WIDTH = 30

    def paint(self, painter, option, index) -> None:
        """Дорисовывает «...» поверх стандартной строки списка."""

        super().paint(painter, option, index)

        rect = option.rect.adjusted(
            option.rect.width() - self.DOT_WIDTH + 2,
            0,
            -4,
            0,
        )

        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        color = (
            "#eaffea"
            if selected
            else ("#c8f0c8" if hovered else "#7fbf8a")
        )

        font = painter.font()
        font.setBold(True)
        font.setPointSize(11)

        painter.save()
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(rect, Qt.AlignCenter, "•••")
        painter.restore()


class ChatListWidget(QListWidget):
    """Список чатов с отдельной зоной кнопки «...» в каждой строке."""

    chat_menu_requested = Signal(int, QPoint)

    MENU_ZONE = 30

    def mousePressEvent(self, event) -> None:
        """Открывает меню при нажатии на три точки справа."""

        if event.button() == Qt.LeftButton:
            position = event.position().toPoint()
            item = self.itemAt(position)

            if item is not None:
                rect = self.visualItemRect(item)

                if position.x() >= rect.right() - self.MENU_ZONE:
                    self.chat_menu_requested.emit(
                        self.row(item),
                        self.viewport().mapToGlobal(position),
                    )
                    event.accept()

                    return

        super().mousePressEvent(event)
