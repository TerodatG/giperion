# Giperion/terminal/ui/widgets/module_button.py                                  v001
# Кнопка модуля.
# Последнее изменение: вынесено из widgets.py.


from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractButton,
)


class ModuleButton(QAbstractButton):
    """Кнопка модуля: пиктограмма и маленький светодиод активации."""

    def __init__(
        self,
        kind: str,
        title: str,
        tooltip: str,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.kind = kind
        self.title = title
        self.base_tooltip = tooltip
        self.hovered = False

        self.setFixedSize(40, 40)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCheckable(kind != "empty")

        if kind == "empty":
            self.setEnabled(False)
            self.setCursor(Qt.ArrowCursor)
            self.setToolTip("Свободный слот")
        else:
            self.setCursor(Qt.PointingHandCursor)
            self.refresh_tooltip()

    def enterEvent(self, event) -> None:
        """Подсвечивает кнопку под мышью."""

        self.hovered = True
        self.update()

        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Убирает подсветку."""

        self.hovered = False
        self.update()

        super().leaveEvent(event)

    def refresh_tooltip(self) -> None:
        """Показывает в подсказке название и, если есть, описание."""

        if self.kind == "empty":
            return

        if not self.base_tooltip:
            self.setToolTip(self.title)

            return

        lines = [self.title, self.base_tooltip]

        if self.isCheckable():
            state = "включён" if self.isChecked() else "выключен"
            lines.append(f"Состояние: {state}.")

        self.setToolTip("\n".join(lines))

    def paintEvent(self, event) -> None:
        """Рисует рамку, пиктограмму и диод состояния."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        width = self.width()
        height = self.height()
        active = self.isChecked() and self.isEnabled()
        hovered = self.hovered and self.isEnabled()

        if active:
            background = QColor(10, 38, 18)
            border = QColor(92, 224, 122)
        elif hovered:
            background = QColor(30, 26, 20)
            border = QColor(150, 112, 78)
        else:
            background = QColor(18, 14, 11)
            border = QColor(58, 46, 37)

        painter.setPen(QPen(border, 1.0))
        painter.setBrush(background)
        painter.drawRoundedRect(
            QRectF(1.0, 1.0, width - 2.0, height - 2.0),
            5.0,
            5.0,
        )

        if active:
            icon_color = QColor(168, 240, 174)
        elif hovered:
            icon_color = QColor(216, 180, 142)
        else:
            icon_color = QColor(140, 122, 104)

        if self.kind == "empty":
            icon_color = QColor(76, 66, 56)

        self._draw_icon(
            painter,
            QRectF(9.0, 8.0, 22.0, 22.0),
            icon_color,
        )

        diode = QPointF(width - 7.0, 7.0)

        if active:
            glow = QRadialGradient(diode, 6.0)
            glow.setColorAt(0.0, QColor(124, 245, 143, 190))
            glow.setColorAt(1.0, QColor(124, 245, 143, 0))

            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(glow))
            painter.drawEllipse(diode, 6.0, 6.0)

            painter.setBrush(QColor(156, 255, 160))
            painter.drawEllipse(diode, 2.7, 2.7)
        else:
            painter.setPen(QPen(QColor(92, 50, 42), 1.0))
            painter.setBrush(QColor(58, 26, 22))
            painter.drawEllipse(diode, 2.5, 2.5)

    def _draw_icon(
        self,
        painter: QPainter,
        rect: QRectF,
        color: QColor,
    ) -> None:
        """Рисует пиктограмму выбранного модуля."""

        painter.save()
        painter.setPen(
            QPen(color, 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        )
        painter.setBrush(Qt.NoBrush)

        center = rect.center()

        if self.kind == "internet":
            painter.drawEllipse(
                QRectF(
                    center.x() - 7,
                    center.y() - 7,
                    14,
                    14,
                )
            )
            painter.drawLine(
                QPointF(center.x() - 7, center.y()),
                QPointF(center.x() + 7, center.y()),
            )
            painter.drawEllipse(
                QRectF(
                    center.x() - 3.5,
                    center.y() - 7,
                    7,
                    14,
                )
            )
        elif self.kind == "models":
            top = QPointF(center.x(), center.y() - 7)
            left = QPointF(center.x() - 7, center.y() + 6)
            right = QPointF(center.x() + 7, center.y() + 6)

            painter.drawLine(top, left)
            painter.drawLine(top, right)
            painter.drawLine(left, right)

            for point in (top, left, right):
                painter.setBrush(QColor(18, 14, 11))
                painter.drawEllipse(point, 2.7, 2.7)
        elif self.kind == "conference":
            # Человек за трибуной с микрофоном.
            painter.drawEllipse(
                QPointF(center.x() - 2, center.y() - 7),
                2.0,
                2.0,
            )
            painter.drawLine(
                QPointF(center.x() - 2, center.y() - 5),
                QPointF(center.x() - 2, center.y() + 1),
            )
            painter.drawLine(
                QPointF(center.x() - 5, center.y() - 2),
                QPointF(center.x() + 1, center.y() - 2),
            )

            podium = QPainterPath()
            podium.moveTo(center.x() - 8, center.y() + 1)
            podium.lineTo(center.x() + 4, center.y() + 1)
            podium.lineTo(center.x() + 2, center.y() + 8)
            podium.lineTo(center.x() - 6, center.y() + 8)
            podium.closeSubpath()
            painter.drawPath(podium)

            painter.drawLine(
                QPointF(center.x() + 6, center.y() + 2),
                QPointF(center.x() + 6, center.y() - 5),
            )
            painter.drawEllipse(
                QPointF(center.x() + 6, center.y() - 7),
                1.6,
                2.2,
            )
        elif self.kind == "voice":
            path = QPainterPath()
            path.moveTo(center.x() - 8, center.y() - 3)
            path.lineTo(center.x() - 4, center.y() - 3)
            path.lineTo(center.x() + 1, center.y() - 8)
            path.lineTo(center.x() + 1, center.y() + 8)
            path.lineTo(center.x() - 4, center.y() + 3)
            path.lineTo(center.x() - 8, center.y() + 3)
            path.closeSubpath()
            painter.drawPath(path)

            painter.drawArc(
                QRectF(
                    center.x() - 1,
                    center.y() - 6,
                    10,
                    12,
                ),
                -60 * 16,
                120 * 16,
            )
            painter.drawArc(
                QRectF(
                    center.x() - 1,
                    center.y() - 9,
                    15,
                    18,
                ),
                -55 * 16,
                110 * 16,
            )
        elif self.kind == "personality":
            # Витрувианская фигура с раскинутыми руками и ногами.
            painter.drawEllipse(
                QPointF(center.x(), center.y() - 6),
                1.8,
                1.8,
            )
            painter.drawLine(
                QPointF(center.x(), center.y() - 4),
                QPointF(center.x(), center.y() + 1),
            )
            painter.drawLine(
                QPointF(center.x() - 7, center.y() - 1),
                QPointF(center.x() + 7, center.y() - 1),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() + 1),
                QPointF(center.x() - 5, center.y() + 7),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() + 1),
                QPointF(center.x() + 5, center.y() + 7),
            )

            painter.setBrush(color)
            painter.drawEllipse(
                QPointF(center.x(), center.y() - 6),
                1.8,
                1.8,
            )

            for point in (
                QPointF(center.x() - 7, center.y() - 1),
                QPointF(center.x() + 7, center.y() - 1),
                QPointF(center.x() - 5, center.y() + 7),
                QPointF(center.x() + 5, center.y() + 7),
            ):
                painter.drawEllipse(point, 1.1, 1.1)

            painter.setBrush(Qt.NoBrush)
        else:
            painter.drawLine(
                QPointF(center.x() - 6, center.y()),
                QPointF(center.x() + 6, center.y()),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() - 6),
                QPointF(center.x(), center.y() + 6),
            )

        painter.restore()

