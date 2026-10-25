# Giperion/terminal/ui/performance_dialog.py                       v002
# Окно «Производительность»: живые графики нагрузки на компьютер.
# Последнее изменение: несколько видеокарт отдельными строками.

import math
import socket
import threading

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from terminal.core.performance_monitor import (
    VolumeUsage,
    create_monitor,
    format_bitrate,
    format_rate,
    read_gpu_details_list,
)
from terminal.core.system_info import format_bytes
from terminal.ui.dialogs_base import SkinDialog

# Сколько точек держит график и как часто обновляются показатели.
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

        # Сетка: три горизонтали и редкие вертикали.
        painter.setPen(
            QPen(QColor(35, 66, 31, 200), 1.0, Qt.DotLine)
        )

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

        if self._scale_text:
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

        has_data = any(values for values, _ in self._series)

        if not has_data:
            font = painter.font()
            font.setPointSizeF(8.0)

            painter.setFont(font)
            painter.setPen(QColor(79, 122, 87))

            painter.drawText(
                inner,
                Qt.AlignCenter,
                "сбор данных…",
            )
            painter.end()

            return

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

            area = QPainterPath(points[0])

            for point in points[1:]:
                area.lineTo(point)

            area.lineTo(QPointF(points[-1].x(), inner.bottom()))
            area.lineTo(QPointF(points[0].x(), inner.bottom()))
            area.closeSubpath()

            gradient = QLinearGradient(
                inner.topLeft(),
                inner.bottomLeft(),
            )

            top = QColor(color)
            top.setAlpha(95)

            bottom = QColor(color)
            bottom.setAlpha(0)

            gradient.setColorAt(0.0, top)
            gradient.setColorAt(1.0, bottom)

            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawPath(area)

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

            # Свечение на последней точке.
            glow = QColor(color)
            glow.setAlpha(90)

            painter.setPen(Qt.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(points[-1], 4.0, 4.0)

            painter.setBrush(color)
            painter.drawEllipse(points[-1], 2.0, 2.0)

        painter.end()


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


class PerformanceDialog(SkinDialog):
    """Окно с живыми графиками нагрузки на компьютер."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Производительность",
            min_width=740,
            min_height=680,
        )

        self.resize(780, 700)

        self.monitor = create_monitor()

        # История значений для графиков.
        self._series: dict[str, list[float]] = {
            "cpu": [],
            "ram": [],
            "disk": [],
            "net_down": [],
            "net_up": [],
            "gpu": [],
        }

        # Сведения видеокарты приходят из отдельного потока.
        self._gpu_details: list[dict] = []
        self._gpu_stop = threading.Event()
        self._gpu_thread: threading.Thread | None = None

        self._paused = False

        self._build_body()

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)

    # --- Сборка окна ---

    def _build_body(self) -> None:
        """Собирает карточки показателей и подвал окна."""

        layout = self.body_layout

        title = QLabel("ПРОИЗВОДИТЕЛЬНОСТЬ", self)
        title.setObjectName("dialogTitle")

        hint = QLabel(
            "Живые показатели компьютера: те же счётчики, что берёт "
            "Диспетчер задач. График хранит последнюю минуту.",
            self,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.cpu_card = MetricCard(self, "ЦП", COLOR_CPU, 78)
        self.cpu_cores = CoreBars(self)
        self.cpu_card.add_extra(self.cpu_cores)

        self.ram_card = MetricCard(self, "Память", COLOR_RAM, 68)
        self.gpu_card = MetricCard(self, "Видеокарта", COLOR_GPU, 68)
        self.net_card = MetricCard(self, "Сеть", COLOR_NET, 68)
        self.disk_card = MetricCard(self, "Диски", COLOR_DISK, 68)

        self.volumes = VolumeBars(self)
        self.disk_card.add_extra(self.volumes)

        grid.addWidget(self.cpu_card, 0, 0, 1, 2)
        grid.addWidget(self.ram_card, 1, 0)
        grid.addWidget(self.gpu_card, 1, 1)
        grid.addWidget(self.net_card, 2, 0)
        grid.addWidget(self.disk_card, 2, 1)

        self.footer = QLabel("", self)
        self.footer.setObjectName("perfFooter")

        self.pause_button = QPushButton("Пауза", self)
        self.pause_button.setObjectName("perfPauseButton")
        self.pause_button.setCheckable(True)
        self.pause_button.setCursor(Qt.ArrowCursor)
        self.pause_button.setFocusPolicy(Qt.NoFocus)
        self.pause_button.toggled.connect(self._on_pause)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(8)
        footer_row.addWidget(self.footer, 1)
        footer_row.addWidget(self.pause_button)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(grid, 1)
        layout.addLayout(footer_row)

        if self.monitor is None:
            self.footer.setText(
                "Не удалось получить доступ к счётчикам системы."
            )
            self.pause_button.setEnabled(False)

    # --- Обновление ---

    def showEvent(self, event) -> None:
        """Запускает обновление и поток сведений видеокарты."""

        super().showEvent(event)

        if self.monitor is None:
            return

        # Уже показанное окно не должно начинать с ложного всплеска:
        # первый замер только задаёт окно усреднения счётчиков.
        self._prime_monitor()
        self.footer.setText("снимаю первый замер…")
        self._timer.start()

        if self._gpu_thread is None:
            self._gpu_thread = threading.Thread(
                target=self._gpu_loop,
                name="giperion-gpu-details",
                daemon=True,
            )
            self._gpu_thread.start()

    def _prime_monitor(self) -> None:
        """Сбрасывает окно усреднения счётчиков после простоя."""

        if self.monitor is None:
            return

        try:
            self.monitor.sample()
        except Exception:  # noqa: BLE001 — замер всё равно пойдёт дальше
            pass

    def _gpu_loop(self) -> None:
        """Опрашивает видеокарту в фоне, чтобы окно не подвисало."""

        while not self._gpu_stop.is_set():
            details = read_gpu_details_list()

            if details:
                self._gpu_details = details

            self._gpu_stop.wait(1.0)

    def _on_pause(self, paused: bool) -> None:
        """Останавливает и возобновляет обновление показателей."""

        self._paused = bool(paused)
        self.pause_button.setText("Дальше" if paused else "Пауза")

        if not paused:
            self._prime_monitor()
            self._timer.start()

    def _push(self, key: str, value: float) -> None:
        """Добавляет точку в историю показателя."""

        series = self._series[key]
        series.append(float(value))

        if len(series) > SERIES_POINTS:
            del series[: len(series) - SERIES_POINTS]

    def _tick(self) -> None:
        """Снимает очередной замер и обновляет карточки."""

        if self._paused or self.monitor is None:
            return

        try:
            sample = self.monitor.sample()

            self._update_cpu(sample)
            self._update_ram(sample)
            self._update_gpu(sample)
            self._update_network(sample)
            self._update_disks(sample)
        except Exception as error:  # noqa: BLE001 — окно не должно падать
            self._timer.stop()
            self.footer.setText(
                f"Счётчики системы недоступны: {error}"
            )

            return

        host = socket.gethostname()
        self.footer.setText(
            f"● обновление раз в секунду · {host} · "
            f"система работает {_format_uptime(sample.uptime)}"
        )

    def _update_cpu(self, sample) -> None:
        """Обновляет карточку процессора."""

        self._push("cpu", sample.cpu_percent)

        self.cpu_card.set_value(f"{sample.cpu_percent:.0f}%")
        self.cpu_card.chart.set_series(
            [(self._series["cpu"], COLOR_CPU)],
            100.0,
            "100%",
        )

        threads = len(sample.cpu_cores)
        frequency = ""

        if sample.cpu_frequency_mhz:
            gigahertz = sample.cpu_frequency_mhz / 1000.0
            frequency = (
                f" · {gigahertz:.1f}".replace(".", ",") + " ГГц"
            )

        self.cpu_card.set_detail(f"потоков: {threads}{frequency}")
        self.cpu_cores.set_loads(sample.cpu_cores)

    def _update_ram(self, sample) -> None:
        """Обновляет карточку оперативной памяти."""

        self._push("ram", sample.ram_percent)

        used = max(0, sample.ram_total - sample.ram_available)

        self.ram_card.set_value(f"{sample.ram_percent:.0f}%")
        self.ram_card.chart.set_series(
            [(self._series["ram"], COLOR_RAM)],
            100.0,
            "100%",
        )
        self.ram_card.set_detail(
            f"{format_bytes(used)} из {format_bytes(sample.ram_total)}"
        )

    def _update_gpu(self, sample) -> None:
        """Обновляет карточку видеокарты или список видеокарт."""

        details_list = list(self._gpu_details or [])
        primary = details_list[0] if details_list else {}

        gpu_percent = sample.gpu_percent

        if primary:
            gpu_percent = float(
                primary.get("utilization") or 0.0
            )

        self._push("gpu", gpu_percent)

        self.gpu_card.set_value(f"{gpu_percent:.0f}%")
        self.gpu_card.chart.set_series(
            [(self._series["gpu"], COLOR_GPU)],
            100.0,
            "100%",
        )

        if len(details_list) > 1:
            self._update_multiple_gpus(details_list)

            return

        self.gpu_card.title.setText("ВИДЕОКАРТА")
        parts: list[str] = []

        name = str(primary.get("name") or "видеокарта")

        if len(name) > 26:
            name = name[:25] + "…"

        parts.append(name)

        temperature = primary.get("temperature") or 0.0

        if temperature:
            parts.append(f"{temperature:.0f} °C")

        power = primary.get("power") or 0.0

        if power:
            parts.append(f"{power:.0f} Вт")

        used = (
            primary.get("memory_used")
            or sample.gpu_memory_used
            or 0
        )
        total = (
            primary.get("memory_total")
            or sample.gpu_memory_total
            or 0
        )

        if used and total:
            parts.append(f"{format_bytes(used)} / {format_bytes(total)}")
        elif used:
            parts.append(f"{format_bytes(used)} видеопамяти")

        self.gpu_card.set_detail(" · ".join(parts))

    def _update_multiple_gpus(self, details_list: list[dict]) -> None:
        """Показывает несколько видеокарт отдельными строками."""

        self.gpu_card.title.setText("ВИДЕОКАРТЫ")

        lines = []

        for index, gpu in enumerate(details_list[:3]):
            name = str(gpu.get("name") or f"GPU {index}")

            if len(name) > 22:
                name = name[:21] + "…"

            parts = [
                f"GPU{index}: {name}",
                f"{float(gpu.get('utilization') or 0.0):.0f}%",
            ]

            temperature = gpu.get("temperature") or 0.0

            if temperature:
                parts.append(f"{temperature:.0f} °C")

            power = gpu.get("power") or 0.0

            if power:
                parts.append(f"{power:.0f} Вт")

            used = gpu.get("memory_used") or 0
            total = gpu.get("memory_total") or 0

            if used and total:
                parts.append(
                    f"{format_bytes(used)} / {format_bytes(total)}"
                )

            lines.append(" · ".join(parts))

        if len(details_list) > 3:
            lines.append(f"… ещё {len(details_list) - 3}")

        self.gpu_card.set_detail("\n".join(lines))

    def _update_network(self, sample) -> None:
        """Обновляет карточку сети."""

        self._push("net_down", sample.net_down_bps)
        self._push("net_up", sample.net_up_bps)

        peak = max(
            max(self._series["net_down"], default=0.0),
            max(self._series["net_up"], default=0.0),
        )
        scale = _rate_scale(peak)

        self.net_card.set_value(format_bitrate(sample.net_down_bps))
        self.net_card.chart.set_series(
            [
                (self._series["net_down"], COLOR_NET),
                (self._series["net_up"], COLOR_NET_UP),
            ],
            scale,
            format_bitrate(scale),
        )
        self.net_card.set_detail(
            f"приём {format_bitrate(sample.net_down_bps)} · "
            f"отдача {format_bitrate(sample.net_up_bps)}"
        )

    def _update_disks(self, sample) -> None:
        """Обновляет карточку дисков."""

        self._push("disk", sample.disk_percent)

        self.disk_card.set_value(f"{sample.disk_percent:.0f}%")
        self.disk_card.chart.set_series(
            [(self._series["disk"], COLOR_DISK)],
            100.0,
            "100%",
        )

        detail = (
            f"чтение {format_rate(sample.disk_read_bps)} · "
            f"запись {format_rate(sample.disk_write_bps)}"
        )

        if sample.disk_queue >= 0.5:
            detail += " · очередь " + f"{sample.disk_queue:.1f}"

        self.disk_card.set_detail(detail)
        self.volumes.set_volumes(sample.volumes)

    # --- Завершение ---

    def closeEvent(self, event) -> None:
        """Останавливает таймер, поток и счётчики."""

        self._timer.stop()
        self._gpu_stop.set()

        if self.monitor is not None:
            self.monitor.close()

        super().closeEvent(event)
