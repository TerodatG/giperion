# Giperion/app/ui/widgets.py                                       v005
# Самостоятельные виджеты окна: пиктограммы, светодиоды, модули, скрепка.
# Последнее изменение: пиктограмма сената — человек за трибуной.

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
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
    QPushButton,
    QSizeGrip,
    QWidget,
)


class SideIconButton(QPushButton):
    """Квадратная кнопка боковой панели с нарисованной пиктограммой."""

    def __init__(
        self,
        icon_name: str,
        tooltip: str,
        parent=None,
    ) -> None:
        super().__init__("", parent)

        self.icon_name = icon_name

        self.setObjectName("sideIconButton")
        self.setFixedSize(46, 42)
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


class StatusLed(QWidget):
    """Пульсирующий светодиод на планке заголовка."""

    def __init__(self, parent=None) -> None:
        """Создаёт светодиод и запускает пульс."""

        super().__init__(parent)

        self.setObjectName("statusLed")
        self.setFixedSize(16, 16)

        self.phase = 0.0

        self.timer = QTimer(self)
        self.timer.setInterval(70)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self) -> None:
        """Двигает фазу свечения."""

        self.phase = (self.phase + 0.06) % 1.0

        self.update()

    def paintEvent(self, event) -> None:
        """Рисует ядро светодиода и его ореол."""

        level = 0.45 + 0.55 * math.sin(self.phase * 2 * math.pi)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        center = QPointF(self.width() / 2, self.height() / 2)
        radius = self.width() / 2 - 3.0

        glow = QRadialGradient(center, radius * 2.0)
        glow.setColorAt(
            0.0, QColor(255, 120, 80, int(210 * level))
        )
        glow.setColorAt(
            0.45, QColor(255, 74, 40, int(90 * level))
        )
        glow.setColorAt(1.0, QColor(120, 20, 10, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(center, radius * 2.0, radius * 2.0)

        core = QColor(255, 190, 170)
        core.setAlpha(int(200 + 55 * level))

        painter.setBrush(core)
        painter.drawEllipse(center, radius * 0.75, radius * 0.75)


class LedMeter(QWidget):
    """Горизонтальная светодиодная шкала, как на пультах станции."""

    # Цвета сегментов слева направо: зелёный, жёлтый, красный.
    SEGMENT_COLORS = (
        QColor(96, 232, 128),
        QColor(240, 216, 88),
        QColor(255, 116, 64),
    )

    # Число сегментов шкалы.
    SEGMENTS = 12

    def __init__(self, parent=None) -> None:
        """Создаёт шкалу и запускает мерцание последнего сегмента."""

        super().__init__(parent)

        self.setObjectName("ledMeter")
        self.setFixedSize(112, 20)

        self.level = 0.0
        self.phase = 0.0

        self.timer = QTimer(self)
        self.timer.setInterval(90)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def set_level(self, percent: float) -> None:
        """Задаёт заполнение шкалы в процентах."""

        self.level = max(0.0, min(100.0, float(percent)))

        self.update()

    def _tick(self) -> None:
        """Двигает фазу мерцания верхнего сегмента."""

        self.phase = (self.phase + 0.12) % 1.0

        self.update()

    def paintEvent(self, event) -> None:
        """Рисует сегменты шкалы."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        width = self.width()
        height = self.height()

        # Тёмная панель под сегментами.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(11, 9, 8))
        painter.drawRoundedRect(
            QRectF(0, 0, width, height), 4.0, 4.0
        )

        painter.setPen(QPen(QColor(58, 46, 37), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(
            QRectF(0.5, 0.5, width - 1, height - 1), 4.0, 4.0
        )

        margin = 3.5
        gap = 2.0
        segment_width = (
            width
            - margin * 2
            - gap * (self.SEGMENTS - 1)
        ) / self.SEGMENTS

        filled = int(
            round(self.level / 100.0 * self.SEGMENTS)
        )

        pulse = 0.5 + 0.5 * math.sin(self.phase * 2 * math.pi)

        painter.setPen(Qt.NoPen)

        for index in range(self.SEGMENTS):
            left = margin + index * (segment_width + gap)

            rect = QRectF(
                left,
                margin,
                segment_width,
                height - margin * 2,
            )

            color = self.SEGMENT_COLORS[
                min(index * 3 // self.SEGMENTS, 2)
            ]

            if index < filled:
                if index == filled - 1:
                    color = color.lighter(
                        int(100 + 35 * pulse)
                    )
            else:
                color = QColor(color)
                color.setAlpha(26)

            painter.setBrush(color)
            painter.drawRoundedRect(rect, 1.6, 1.6)


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
        elif self.kind == "files":
            path = QPainterPath()
            path.moveTo(center.x() - 8, center.y() - 6)
            path.lineTo(center.x() - 2, center.y() - 6)
            path.lineTo(center.x() + 1, center.y() - 3)
            path.lineTo(center.x() + 8, center.y() - 3)
            path.lineTo(center.x() + 8, center.y() + 7)
            path.lineTo(center.x() - 8, center.y() + 7)
            path.closeSubpath()
            painter.drawPath(path)
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


class PaperclipButton(QAbstractButton):
    """Скрепка в левом нижнем углу поля ввода."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.allowed = True
        self.hovered = False

        self.setFixedSize(28, 28)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Добавить текстовый файл")
        self.setStyleSheet("background: transparent; border: none;")

    def set_allowed(self, allowed: bool) -> None:
        """Показывает, разрешён ли сейчас доступ к файлам."""

        self.allowed = bool(allowed)

        if self.allowed:
            self.setToolTip("Добавить текстовый файл")
        else:
            self.setToolTip(
                "Доступ к файлам выключен. "
                "Включи модуль «Файлы ПК»."
            )

        self.update()

    def enterEvent(self, event) -> None:
        """Подсвечивает скрепку под мышью."""

        self.hovered = True
        self.update()

        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Убирает подсветку."""

        self.hovered = False
        self.update()

        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        """Рисует скрепку без системной рамки кнопки."""

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
            if self.allowed
            else QColor(92, 78, 66)
        )

        painter.save()

        center = QPointF(
            self.width() / 2,
            self.height() / 2,
        )

        painter.translate(center)
        painter.rotate(-20)
        painter.translate(-center)

        painter.setPen(
            QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        )
        painter.setBrush(Qt.NoBrush)

        painter.drawRoundedRect(
            QRectF(
                center.x() - 6,
                center.y() - 9,
                12,
                18,
            ),
            6.0,
            6.0,
        )
        painter.drawRoundedRect(
            QRectF(
                center.x() - 2.6,
                center.y() - 6,
                5.2,
                12,
            ),
            2.6,
            2.6,
        )

        painter.restore()


class FuturisticGrip(QSizeGrip):
    """Размерный уголок в стиле окна: три диагональные риски."""

    def paintEvent(self, event) -> None:
        """Рисует свой узор вместо системного."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        pen = QPen(QColor(190, 150, 110, 190))
        pen.setWidthF(1.4)

        painter.setPen(pen)

        width = self.width()
        height = self.height()

        for offset in (4, 8, 12):
            painter.drawLine(
                width - offset - 2,
                height - 2,
                2,
                height - offset - 2,
            )

