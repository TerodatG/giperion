# Giperion/terminal/ui/performance_dialog.py                       v002
# Окно «Производительность»: живые графики нагрузки на компьютер.
# Последнее изменение: несколько видеокарт отдельными строками.

import socket
import threading

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

from terminal.core.performance_monitor import (
    create_monitor,
    format_bitrate,
    format_rate,
    read_gpu_details_list,
)
from terminal.core.system_info import format_bytes
from terminal.ui.dialogs_base import SkinDialog
from terminal.ui.performance_charts import (
    COLOR_CPU,
    COLOR_DISK,
    COLOR_GPU,
    COLOR_NET,
    COLOR_NET_UP,
    COLOR_RAM,
    SERIES_POINTS,
    TICK_MS,
    CoreBars,
    MetricCard,
    VolumeBars,
    _format_uptime,
    _rate_scale,
)

# Сколько точек держит график и как часто обновляются показатели.


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
