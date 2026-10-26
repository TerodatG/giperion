# Giperion/terminal/ui/widgets/side_icon.py                                  v001
# Кнопка боковой панели с пиктограммой.
# Последнее изменение: вынесено из widgets.py.

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QPushButton,
)


class SideIconButton(QPushButton):
    """Квадратная кнопка боковой панели с нарисованной пиктограммой."""

    def __init__(
        self,
        icon_name: str,
        tooltip: str,
        parent=None,
        size: tuple[int, int] = (46, 42),
    ) -> None:
        super().__init__("", parent)

        self.icon_name = icon_name

        self.setObjectName("sideIconButton")
        self.setFixedSize(size[0], size[1])
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, event) -> None:
        """Рисует рамку кнопки и её пиктограмму."""

        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        color = QColor("#9dd6a0" if self.underMouse() else "#7cc486")
        pen = QPen(
            color,
            1.7,
            Qt.SolidLine,
            Qt.RoundCap,
            Qt.RoundJoin,
        )

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        width = self.width()
        height = self.height()
        center_x = width / 2.0
        center_y = height / 2.0

        if self.icon_name == "settings":
            self._paint_gear(painter, center_x, center_y)
        elif self.icon_name == "models":
            self._paint_people(painter, center_x, center_y)
        elif self.icon_name == "personalities":
            self._paint_personalities(
                painter,
                center_x,
                center_y,
            )
        elif self.icon_name == "conference":
            self._paint_conference(
                painter,
                center_x,
                center_y,
            )
        elif self.icon_name == "workshop":
            self._paint_workshop(
                painter,
                center_x,
                center_y,
            )
        elif self.icon_name == "drone":
            self._paint_drone(painter, center_x, center_y)
        elif self.icon_name == "performance":
            self._paint_performance(
                painter,
                center_x,
                center_y,
            )
        elif self.icon_name == "update":
            self._paint_update(painter, center_x, center_y)
        elif self.icon_name == "help":
            self._paint_help(painter, center_x, center_y)
        else:
            self._paint_skills(painter, center_x, center_y)

    @staticmethod
    def _paint_gear(painter, center_x: float, center_y: float) -> None:
        """Рисует шестерёнку настроек."""

        for step in range(8):
            painter.save()
            painter.translate(center_x, center_y)
            painter.rotate(step * 45)
            painter.drawLine(QPointF(0, -8), QPointF(0, -12))
            painter.restore()

        painter.drawEllipse(QPointF(center_x, center_y), 8, 8)
        painter.drawEllipse(QPointF(center_x, center_y), 3, 3)

    @staticmethod
    def _paint_workshop(painter, center_x: float, center_y: float) -> None:
        """Рисует скрещённые молоток и гаечный ключ."""

        # Молоток: рукоять и повёрнутая голова.
        painter.drawLine(
            QPointF(center_x - 8, center_y + 8),
            QPointF(center_x + 4, center_y - 4),
        )
        painter.save()
        painter.translate(center_x + 6, center_y - 6)
        painter.rotate(45)
        painter.drawRect(QRectF(-2.5, -6, 5, 12))
        painter.restore()

        # Гаечный ключ: рукоять и раскрытая пасть.
        painter.drawLine(
            QPointF(center_x + 8, center_y + 8),
            QPointF(center_x - 4, center_y - 4),
        )
        painter.drawArc(
            QRectF(center_x - 13, center_y - 13, 9, 9),
            30 * 16,
            300 * 16,
        )

    @staticmethod
    def _paint_people(painter, center_x: float, center_y: float) -> None:
        """Рисует человека, а за ним — андроида."""

        # Андроид за спиной: голова, антенна и плечи.
        painter.drawEllipse(
            QPointF(center_x + 8, center_y - 7),
            3.4,
            3.4,
        )
        painter.drawLine(
            QPointF(center_x + 8, center_y - 12),
            QPointF(center_x + 8, center_y - 15),
        )
        painter.drawEllipse(
            QPointF(center_x + 8, center_y - 16),
            1.2,
            1.2,
        )
        painter.drawRoundedRect(
            QRectF(center_x + 2, center_y, 14, 11),
            5,
            5,
        )

        # Человек впереди.
        painter.setBrush(QColor("#05100a"))
        painter.drawEllipse(
            QPointF(center_x - 5, center_y - 7),
            4.4,
            4.4,
        )
        painter.drawRoundedRect(
            QRectF(center_x - 13, center_y, 17, 12),
            6,
            6,
        )

    @staticmethod
    def _paint_personalities(
        painter,
        center_x: float,
        center_y: float,
    ) -> None:
        """Рисует маску личности с матрицей решений."""

        # Контур лица.
        painter.drawEllipse(
            QRectF(center_x - 8, center_y - 11, 16, 18)
        )

        # Плечи.
        painter.drawArc(
            QRectF(center_x - 12, center_y + 5, 24, 13),
            0,
            180 * 16,
        )

        # Матрица в области лба.
        for column in (-3.0, 0.0, 3.0):
            for row in (-6.0, -2.5):
                painter.drawEllipse(
                    QPointF(center_x + column, center_y + row),
                    0.9,
                    0.9,
                )

    @staticmethod
    def _paint_conference(
        painter,
        center_x: float,
        center_y: float,
    ) -> None:
        """Рисует человека за трибуной с микрофоном."""

        painter.drawEllipse(
            QPointF(center_x - 2, center_y - 7),
            2.2,
            2.2,
        )
        painter.drawLine(
            QPointF(center_x - 2, center_y - 5),
            QPointF(center_x - 2, center_y + 1),
        )
        painter.drawLine(
            QPointF(center_x - 5, center_y - 2),
            QPointF(center_x + 1, center_y - 2),
        )

        podium = QPainterPath()
        podium.moveTo(center_x - 8, center_y + 1)
        podium.lineTo(center_x + 4, center_y + 1)
        podium.lineTo(center_x + 2, center_y + 8)
        podium.lineTo(center_x - 6, center_y + 8)
        podium.closeSubpath()
        painter.drawPath(podium)

        painter.drawLine(
            QPointF(center_x + 6, center_y + 2),
            QPointF(center_x + 6, center_y - 5),
        )
        painter.drawEllipse(
            QPointF(center_x + 6, center_y - 7),
            1.6,
            2.2,
        )

    @staticmethod
    def _paint_skills(painter, center_x: float, center_y: float) -> None:
        """Рисует нейронный узел — символ освоенных умений."""

        for step in range(6):
            angle = math.radians(step * 60 - 90)
            point = QPointF(
                center_x + math.cos(angle) * 10,
                center_y + math.sin(angle) * 10,
            )

            painter.drawLine(
                QPointF(center_x, center_y),
                point,
            )
            painter.drawEllipse(point, 1.8, 1.8)

        painter.drawEllipse(QPointF(center_x, center_y), 2.6, 2.6)

    @staticmethod
    def _paint_help(painter, center_x: float, center_y: float) -> None:
        """Рисует знак вопроса в круге для кнопки справки."""

        painter.drawEllipse(
            QPointF(center_x, center_y),
            9.5,
            9.5,
        )

        question = QPainterPath()
        question.moveTo(center_x - 3.2, center_y - 4.6)
        question.quadTo(
            center_x - 3.2,
            center_y - 8.6,
            center_x,
            center_y - 8.6,
        )
        question.quadTo(
            center_x + 3.6,
            center_y - 8.6,
            center_x + 3.6,
            center_y - 5.2,
        )
        question.quadTo(
            center_x + 3.6,
            center_y - 2.2,
            center_x,
            center_y - 0.4,
        )
        question.lineTo(center_x, center_y + 1.6)

        painter.drawPath(question)
        painter.drawEllipse(
            QPointF(center_x, center_y + 5.6),
            1.0,
            1.0,
        )

    @staticmethod
    def _paint_drone(painter, center_x: float, center_y: float) -> None:
        """Рисует квадрокоптер — дрон терминала."""

        # Лучи и винты по четырём углам.
        for offset_x, offset_y in (
            (-8.0, -6.5),
            (8.0, -6.5),
            (-8.0, 6.5),
            (8.0, 6.5),
        ):
            painter.drawLine(
                QPointF(
                    center_x + offset_x * 0.34,
                    center_y + offset_y * 0.36,
                ),
                QPointF(center_x + offset_x, center_y + offset_y),
            )
            painter.drawEllipse(
                QPointF(
                    center_x + offset_x,
                    center_y + offset_y,
                ),
                3.1,
                3.1,
            )

        # Корпус.
        painter.drawRoundedRect(
            QRectF(
                center_x - 4.2,
                center_y - 3.2,
                8.4,
                6.4,
            ),
            2.2,
            2.2,
        )

        # Антенна с сигнальным огоньком.
        painter.drawLine(
            QPointF(center_x, center_y - 3.2),
            QPointF(center_x, center_y - 6.6),
        )
        painter.drawEllipse(
            QPointF(center_x, center_y - 7.8),
            1.1,
            1.1,
        )


    @staticmethod
    def _paint_performance(
        painter,
        center_x: float,
        center_y: float,
    ) -> None:
        """Рисует столбики нагрузки — значок производительности."""

        painter.drawLine(
            QPointF(center_x - 11, center_y + 9),
            QPointF(center_x + 11, center_y + 9),
        )

        for offset_x, height in ((-10.0, 7.0), (-3.5, 12.0), (3.0, 17.0)):
            painter.drawRoundedRect(
                QRectF(
                    center_x + offset_x,
                    center_y + 9 - height,
                    5.0,
                    height,
                ),
                1.6,
                1.6,
            )


    @staticmethod
    def _paint_update(
        painter,
        center_x: float,
        center_y: float,
    ) -> None:
        """Рисует круговую стрелку — значок обновления."""

        radius = 8.6
        start_angle = 45.0
        span_angle = 250.0

        painter.drawArc(
            QRectF(
                center_x - radius,
                center_y - radius,
                radius * 2,
                radius * 2,
            ),
            int(start_angle * 16),
            int(span_angle * 16),
        )

        # Наконечник: залитый треугольник по касательной к дуге.
        angle = math.radians(start_angle + span_angle)
        tip_x = center_x + radius * math.cos(angle)
        tip_y = center_y - radius * math.sin(angle)

        tangent_x = -math.sin(angle)
        tangent_y = -math.cos(angle)
        normal_x = -tangent_y
        normal_y = tangent_x

        base_x = tip_x - tangent_x * 2.0
        base_y = tip_y - tangent_y * 2.0

        arrow = QPainterPath()
        arrow.moveTo(
            QPointF(
                tip_x + tangent_x * 3.0,
                tip_y + tangent_y * 3.0,
            )
        )
        arrow.lineTo(
            QPointF(
                base_x + normal_x * 3.2,
                base_y + normal_y * 3.2,
            )
        )
        arrow.lineTo(
            QPointF(
                base_x - normal_x * 3.2,
                base_y - normal_y * 3.2,
            )
        )
        arrow.closeSubpath()

        color = painter.pen().color()

        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawPath(arrow)
        painter.restore()

