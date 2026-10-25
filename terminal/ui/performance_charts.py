# Giperion/terminal/ui/performance_charts.py                           v001
# Графики производительности: искры, ядра, тома и карточки.
# Последнее изменение: вынесено из performance_dialog.

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from terminal.core.performance_monitor import VolumeUsage
from terminal.core.system_info import format_bytes

SERIES_POINTS = 60
TICK_MS = 1000

# Цвета показателей — в палитре терминала.
COLOR_CPU = "#7cf58f"
COLOR_RAM = "#d8b48e"
COLOR_DISK = "#e8c96a"
COLOR_NET = "#6fd8c8"
COLOR_NET_UP = "#e8a06a"
COLOR_GPU = "#9fc6ff"

# Цвета предупреждения и перегрузки.
COLOR_WARN = "#f0c85a"
COLOR_ALERT = "#ff7a5c"


def _percent_color(percent: float) -> QColor:
    """Выбирает цвет шкалы по уровню нагрузки."""

    if percent >= 85:
        return QColor(COLOR_ALERT)

    if percent >= 60:
        return QColor(COLOR_WARN)

    return QColor(COLOR_CPU)


def _format_uptime(seconds: float) -> str:
    """Пишет время работы системы словами."""

    total = int(max(0.0, seconds))
    days, remainder = divmod(total, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes = remainder // 60

    if days:
        return f"{days} сут {hours} ч"

    if hours:
        return f"{hours} ч {minutes} мин"

    return f"{minutes} мин"


def _rate_scale(peak: float) -> float:
    """Подбирает верхнюю границу графика сети с запасом."""

    target = max(float(peak) * 1.15, 12_500.0)
    magnitude = 10 ** math.floor(math.log10(target))

    for factor in (1.0, 2.0, 2.5, 5.0, 10.0):
        vertical = factor * magnitude

        if vertical >= target:
            return vertical

    return 10.0 * magnitude


class SparkChart(QWidget):
    """График-искра: заливка под линией и сетка, как на пульте станции."""

    def __init__(self, parent=None, height: int = 74) -> None:
        super().__init__(parent)

        self.setObjectName("sparkChart")
        self.setMinimumHeight(height)
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        self._series: list[tuple[list[float], QColor]] = []
        self._maximum = 100.0
        self._scale_text = ""

    def set_series(
        self,
        series: list[tuple[list[float], str]],
        maximum: float,
        scale_text: str = "",
    ) -> None:
        """Задаёт линии графика: пары «значения — цвет»."""

        self._series = [
            ([float(value) for value in values], QColor(color))
            for values, color in series
        ]
        self._maximum = max(1e-9, float(maximum))
        self._scale_text = scale_text

        self.update()

    def paintEvent(self, event) -> None:
        """Рисует фон, сетку и линии показателей."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        painter.setPen(QPen(QColor("#1c3520"), 1.0))
        painter.setBrush(QColor(4, 14, 9))
        painter.drawRoundedRect(frame, 4.0, 4.0)

        inner = frame.adjusted(6.0, 9.0, -6.0, -6.0)

        if inner.width() <= 4 or inner.height() <= 4:
            painter.end()

            return

        self._draw_grid(painter, inner, frame)

        if not any(values for values, _ in self._series):
            self._draw_empty(painter, inner)
            painter.end()

            return

        self._draw_series(painter, inner)
        painter.end()

    def _draw_grid(self, painter: QPainter, inner: QRectF, frame: QRectF) -> None:
        """Сетка и подпись масштаба."""

        painter.setPen(QPen(QColor(35, 66, 31, 200), 1.0, Qt.DotLine))

        for step in range(1, 4):
            y = inner.top() + inner.height() * step / 4.0
            painter.drawLine(
                QPointF(inner.left(), y),
                QPointF(inner.right(), y),
            )

        painter.setPen(QPen(QColor(30, 56, 27, 130), 1.0, Qt.DotLine))

        for step in range(1, 6):
            x = inner.left() + inner.width() * step / 6.0
            painter.drawLine(
                QPointF(x, inner.top()),
                QPointF(x, inner.bottom()),
            )

        if not self._scale_text:
            return

        font = painter.font()
        font.setPointSizeF(7.0)
        font.setBold(False)

        painter.setFont(font)
        painter.setPen(QColor(79, 122, 87))
        painter.drawText(
            QRectF(
                inner.left(),
                frame.top() + 1.0,
                inner.width(),
                9.0,
            ),
            Qt.AlignRight | Qt.AlignVCenter,
            self._scale_text,
        )

    def _draw_empty(self, painter: QPainter, inner: QRectF) -> None:
        """Подпись «сбор данных…»."""

        font = painter.font()
        font.setPointSizeF(8.0)

        painter.setFont(font)
        painter.setPen(QColor(79, 122, 87))
        painter.drawText(inner, Qt.AlignCenter, "сбор данных…")

    def _draw_series(self, painter: QPainter, inner: QRectF) -> None:
        """Линии и заливка рядов."""

        step = inner.width() / max(1, SERIES_POINTS - 1)

        for values, color in self._series:
            if not values:
                continue

            points = []
            offset = SERIES_POINTS - len(values)

            for index, value in enumerate(values):
                x = inner.left() + (offset + index) * step
                ratio = min(1.0, max(0.0, value / self._maximum))
                y = inner.bottom() - ratio * inner.height()
                points.append(QPointF(x, y))

            if len(points) == 1:
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(points[0], 2.2, 2.2)

                continue

            self._fill_area(painter, points, inner, color)
            self._draw_line(painter, points, color)
            self._draw_last_point(painter, points[-1], color)

    def _fill_area(self, painter, points, inner, color) -> None:
        """Заливка под линией."""

        area = QPainterPath(points[0])

        for point in points[1:]:
            area.lineTo(point)

        area.lineTo(QPointF(points[-1].x(), inner.bottom()))
        area.lineTo(QPointF(points[0].x(), inner.bottom()))
        area.closeSubpath()

        gradient = QLinearGradient(inner.topLeft(), inner.bottomLeft())
        top = QColor(color)
        top.setAlpha(95)
        bottom = QColor(color)
        bottom.setAlpha(0)
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, bottom)

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(area)

    def _draw_line(self, painter, points, color) -> None:
        """Сама линия ряда."""

        line = QPainterPath(points[0])

        for point in points[1:]:
            line.lineTo(point)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(
            QPen(
                color,
                1.6,
                Qt.SolidLine,
                Qt.RoundCap,
                Qt.RoundJoin,
            )
        )
        painter.drawPath(line)

    def _draw_last_point(self, painter, point, color) -> None:
        """Свечение на последней точке."""

        glow = QColor(color)
        glow.setAlpha(90)

        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(point, 4.0, 4.0)

        painter.setBrush(color)
        painter.drawEllipse(point, 2.0, 2.0)


class CoreBars(QWidget):
    """Полоски загрузки по потокам процессора."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setObjectName("coreBars")
        self.setMinimumHeight(24)
        self.setMaximumHeight(24)
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        # Шире этой полоски ячейка потока не становится: иначе восемь
        # ядер превращаются в восемь широких лент.
        self.MAX_BAR_WIDTH = 18.0

        self._loads: list[float] = []

    def set_loads(self, loads: list[float]) -> None:
        """Задаёт загрузку каждого потока в процентах."""

        self._loads = [max(0.0, min(100.0, float(v))) for v in loads]

        if self._loads:
            summary = " · ".join(
                f"{index + 1}:{value:.0f}%"
                for index, value in enumerate(self._loads)
            )
            self.setToolTip(f"Потоки ЦП — {summary}")
        else:
            self.setToolTip("Потоки ЦП: данных пока нет")

        self.update()

    def paintEvent(self, event) -> None:
        """Рисует по полоске на каждый поток."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        count = len(self._loads)

        if not count:
            painter.end()

            return

        width = self.width()
        gap = 2.0
        bar_width = min(
            self.MAX_BAR_WIDTH,
            max(2.0, (width - gap * (count - 1)) / count),
        )
        height = float(self.height())

        for index, load in enumerate(self._loads):
            left = index * (bar_width + gap)
            track = QRectF(left, 0.0, bar_width, height)

            painter.setPen(QPen(QColor("#1c3520"), 1.0))
            painter.setBrush(QColor(8, 22, 13))
            painter.drawRoundedRect(track, 2.0, 2.0)

            filled = max(1.5, height * load / 100.0)
            fill = QRectF(
                left + 1.0,
                height - filled,
                max(1.0, bar_width - 2.0),
                filled,
            )

            painter.setPen(Qt.NoPen)
            painter.setBrush(_percent_color(load))
            painter.drawRoundedRect(fill, 1.6, 1.6)

        painter.end()


class VolumeBars(QWidget):
    """Занятое место на томах: подпись, шкала и свободный объём."""

    ROW_HEIGHT = 17.0

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setObjectName("volumeBars")
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        self._volumes: list[VolumeUsage] = []

    def set_volumes(self, volumes: list[VolumeUsage]) -> None:
        """Задаёт список томов для отрисовки."""

        self._volumes = list(volumes)
        self.setFixedHeight(
            max(17, int(self.ROW_HEIGHT * max(1, len(self._volumes))))
        )

        self.update()

    def paintEvent(self, event) -> None:
        """Рисует по строке на каждый том."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        font = painter.font()
        font.setPointSizeF(7.5)
        font.setBold(True)
        painter.setFont(font)

        width = float(self.width())

        for index, volume in enumerate(self._volumes):
            top = index * self.ROW_HEIGHT
            used = max(0, volume.total - volume.free)
            ratio = used / volume.total if volume.total else 0.0
            percent = ratio * 100.0

            painter.setPen(QColor(142, 216, 138))
            painter.drawText(
                QRectF(0.0, top, 26.0, self.ROW_HEIGHT),
                Qt.AlignLeft | Qt.AlignVCenter,
                volume.name,
            )

            track = QRectF(28.0, top + 4.5, width - 28.0 - 118.0, 8.0)

            painter.setPen(QPen(QColor("#1c3520"), 1.0))
            painter.setBrush(QColor(8, 22, 13))
            painter.drawRoundedRect(track, 2.0, 2.0)

            if track.width() > 2:
                filled = QRectF(
                    track.left() + 1.0,
                    track.top() + 1.0,
                    max(0.0, (track.width() - 2.0) * ratio),
                    track.height() - 2.0,
                )

                painter.setPen(Qt.NoPen)
                painter.setBrush(_percent_color(percent))
                painter.drawRoundedRect(filled, 1.5, 1.5)

            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor(159, 191, 165))
            painter.drawText(
                QRectF(width - 116.0, top, 116.0, self.ROW_HEIGHT),
                Qt.AlignRight | Qt.AlignVCenter,
                f"{format_bytes(volume.free)} свободно",
            )
            font.setBold(True)
            painter.setFont(font)

        painter.end()


class MetricCard(QWidget):
    """Карточка показателя: заголовок, значение, график и подробности."""

    def __init__(
        self,
        parent,
        title: str,
        accent: str,
        chart_height: int = 74,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("performanceCard")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.accent = accent

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self.title = QLabel(title.upper(), self)
        self.title.setObjectName("perfTitle")

        self.value = QLabel("—", self)
        self.value.setObjectName("perfValue")
        self.value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value.setStyleSheet(f"color: {accent};")

        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.value)

        self.chart = SparkChart(self, chart_height)

        self.detail = QLabel("", self)
        self.detail.setObjectName("perfDetail")
        self.detail.setWordWrap(True)

        layout.addLayout(header)
        layout.addWidget(self.chart)
        layout.addWidget(self.detail)

        self._layout = layout
        self._extras: list[QWidget] = []

    def add_extra(self, widget: QWidget) -> None:
        """Добавляет приставку между графиком и строкой подробностей."""

        position = self._layout.indexOf(self.detail)
        self._layout.insertWidget(position, widget)
        self._extras.append(widget)

    def set_value(self, text: str) -> None:
        """Показывает текущее значение крупным шрифтом."""

        self.value.setText(text)

    def set_detail(self, text: str) -> None:
        """Показывает подробности под графиком."""

        self.detail.setText(text)
