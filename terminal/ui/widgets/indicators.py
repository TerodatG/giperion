# Giperion/terminal/ui/widgets/indicators.py                                  v001
# Светодиод и шкала уровня.
# Последнее изменение: вынесено из widgets.py.

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QWidget,
)


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

