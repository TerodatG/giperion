# Giperion/terminal/core/performance_psutil.py                        v001
# Запасные счётчики через psutil.
# Последнее изменение: вынесено из performance_monitor.

import time

from terminal.core.performance_helpers import _clamp
from terminal.core.performance_types import (
    _VOLUME_CACHE_SECONDS,
    PerformanceSample,
    VolumeUsage,
    _total_memory,
    _uptime_seconds,
    _volumes,
)


class PsutilCounters:
    """Резервный источник показателей — psutil.

    На Windows основной путь — PDH. Этот класс выручает, если счётчики
    недоступны, и работает на других системах.
    """

    def __init__(self) -> None:
        import psutil  # noqa: PLC0415 — модуль нужен только здесь

        self._psutil = psutil
        self._ram_total = _total_memory()
        self._volumes: list[VolumeUsage] = []
        self._volumes_time = -_VOLUME_CACHE_SECONDS

        # Первый вызов только запускает подсчёт дельт.
        psutil.cpu_percent(interval=None, percpu=True)

    def _current_volumes(self) -> list[VolumeUsage]:
        """Отдаёт список томов с тем же кешем, что и PDH-путь."""

        now = time.monotonic()

        if now - self._volumes_time >= _VOLUME_CACHE_SECONDS:
            self._volumes = _volumes()
            self._volumes_time = now

        return list(self._volumes)

    def sample(self) -> PerformanceSample:
        """Снимает один снимок производительности через psutil."""

        psutil = self._psutil

        sample = PerformanceSample(
            ram_total=self._ram_total,
            uptime=_uptime_seconds(),
            source="psutil",
        )

        sample.cpu_cores = [
            _clamp(value)
            for value in psutil.cpu_percent(interval=None, percpu=True)
        ]

        if sample.cpu_cores:
            sample.cpu_percent = _clamp(
                sum(sample.cpu_cores) / len(sample.cpu_cores)
            )

        frequency = psutil.cpu_freq()

        if frequency is not None:
            sample.cpu_frequency_mhz = float(frequency.current)

        memory = psutil.virtual_memory()
        sample.ram_total = int(memory.total)
        sample.ram_available = int(memory.available)
        sample.ram_percent = _clamp(memory.percent)

        # Сеть сравниваем с прошлым замером: psutil отдаёт счётчики.
        try:
            net = psutil.net_io_counters()
        except (OSError, RuntimeError):
            net = None

        if net is not None:
            now = time.monotonic()
            previous = getattr(self, "_net_previous", None)

            if previous is not None:
                elapsed = max(1e-3, now - previous[0])
                sample.net_down_bps = max(
                    0.0,
                    (net.bytes_recv - previous[1]) / elapsed,
                )
                sample.net_up_bps = max(
                    0.0,
                    (net.bytes_sent - previous[2]) / elapsed,
                )

            self._net_previous = (now, net.bytes_recv, net.bytes_sent)

        sample.volumes = self._current_volumes()

        return sample

    def close(self) -> None:
        """Резервному источнику закрывать нечего."""

