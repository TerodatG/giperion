# Giperion/terminal/ui/widgets/attach.py                                  v001
# Кнопка вложения.
# Последнее изменение: вынесено из widgets.py.


from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QAbstractButton,
)


class AttachButton(QAbstractButton):
    """Кнопка «+» в левом нижнем углу поля ввода: меню вложений."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.hovered = False

        self.setFixedSize(28, 28)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Добавить вложение")
        self.setAccessibleName("Добавить вложение")
        self.setStyleSheet("background: transparent; border: none;")

    def enterEvent(self, event) -> None:
        """Подсвечивает плюс под мышью."""

        self.hovered = True
        self.update()

        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Убирает подсветку."""

        self.hovered = False
        self.update()

        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        """Рисует плюс без системной рамки кнопки."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self.hovered:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(30, 58, 34, 190))
            painter.drawRoundedRect(
                QRectF(0, 0, self.width(), self.height()),
                5.0,
                5.0,
            )

        color = (
            QColor(157, 214, 160)
            if self.hovered
            else QColor(124, 196, 134)
        )

        painter.setPen(
            QPen(color, 1.9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        )
        painter.setBrush(Qt.NoBrush)

        center = QPointF(
            self.width() / 2,
            self.height() / 2,
        )

        painter.drawLine(
            QPointF(center.x() - 6.5, center.y()),
            QPointF(center.x() + 6.5, center.y()),
        )
        painter.drawLine(
            QPointF(center.x(), center.y() - 6.5),
            QPointF(center.x(), center.y() + 6.5),
        )

