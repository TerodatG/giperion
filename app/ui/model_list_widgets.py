# Giperion/app/ui/model_list_widgets.py                             v001
# Список моделей: значок «Сенатор» у первых трёх участников совета.
# Последнее изменение: пиктограмма человека за трибуной справа от названия.

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

# Роль элемента списка: показывать ли значок сенатора.
SENATOR_ICON_ROLE = Qt.UserRole + 1


def draw_senator_icon(
    painter,
    rect: QRect,
    color: str,
) -> None:
    """Рисует человека за трибуной — как на кнопке конференции."""

    painter.save()
    painter.setRenderHint(QPainter.Antialiasing, True)

    pen = QPen(QColor(color))
    pen.setWidthF(max(1.0, rect.width() / 16))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    x = float(rect.x())
    y = float(rect.y())
    size = float(rect.width())

    center_x = x + size * 0.42

    # Голова и корпус человека.
    painter.drawEllipse(
        QPointF(center_x, y + size * 0.20),
        size * 0.09,
        size * 0.09,
    )
    painter.drawLine(
        QPointF(center_x, y + size * 0.30),
        QPointF(center_x, y + size * 0.49),
    )
    painter.drawLine(
        QPointF(center_x - size * 0.15, y + size * 0.38),
        QPointF(center_x + size * 0.17, y + size * 0.38),
    )

    # Трибуна.
    podium = QPainterPath()
    podium.moveTo(x + size * 0.14, y + size * 0.49)
    podium.lineTo(x + size * 0.70, y + size * 0.49)
    podium.lineTo(x + size * 0.63, y + size * 0.84)
    podium.lineTo(x + size * 0.21, y + size * 0.84)
    podium.closeSubpath()
    painter.drawPath(podium)

    # Микрофон на стойке.
    painter.drawLine(
        QPointF(x + size * 0.80, y + size * 0.52),
        QPointF(x + size * 0.80, y + size * 0.32),
    )
    painter.drawEllipse(
        QPointF(x + size * 0.80, y + size * 0.27),
        size * 0.07,
        size * 0.10,
    )

    painter.restore()


class ModelListDelegate(QStyledItemDelegate):
    """Дорисовывает справа значок сенатора поверх строки списка."""

    ICON_SIZE = 18
    RIGHT_MARGIN = 10
    TOP_MARGIN = 7

    def paint(self, painter, option, index) -> None:
        """Сначала обычная строка, затем значок должности."""

        super().paint(painter, option, index)

        if not index.data(SENATOR_ICON_ROLE):
            return

        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        color = (
            "#eaffea"
            if selected
            else ("#ffe2a8" if hovered else "#ffd479")
        )

        icon_rect = QRect(
            option.rect.right() - self.ICON_SIZE - self.RIGHT_MARGIN,
            option.rect.top() + self.TOP_MARGIN,
            self.ICON_SIZE,
            self.ICON_SIZE,
        )

        draw_senator_icon(painter, icon_rect, color)
