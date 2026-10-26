# Giperion/terminal/core/performance_monitor.py                    v003
# Живые показатели компьютера: ЦП, память, диски, сеть и видеокарты.
# Последнее изменение: чтение всех видеокарт NVIDIA.

import os
import subprocess
import time

from shared.process_tools import hidden_process_options
from terminal.core.performance_helpers import (
    _clamp,  # noqa: F401 — реэкспорт для тестов
    _sum_filtered,  # noqa: F401 — реэкспорт для тестов
)
from terminal.core.performance_psutil import PsutilCounters
from terminal.core.performance_types import (
    _GPU_CACHE_SECONDS,
    PerformanceSample,  # noqa: F401 — реэкспорт
    VolumeUsage,  # noqa: F401 — реэкспорт
)
from terminal.core.performance_windows import WindowsCounters


def format_rate(bytes_per_second: float) -> str:
    """Пишет скорость потока данных в удобных единицах."""

    value = max(0.0, float(bytes_per_second))
    units = ("Б/с", "КБ/с", "МБ/с", "ГБ/с")
    index = 0

    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1

    if index == 0:
        return f"{int(value)} {units[index]}"

    return f"{value:.1f}".replace(".", ",") + f" {units[index]}"


def format_bitrate(bytes_per_second: float) -> str:
    """Пишет скорость сети в битах — так её показывают провайдеры."""

    value = max(0.0, float(bytes_per_second)) * 8

    units = ("бит/с", "Кбит/с", "Мбит/с", "Гбит/с")
    index = 0

    while value >= 1000 and index < len(units) - 1:
        value /= 1000
        index += 1

    if index == 0:
        return f"{int(value)} {units[index]}"

    return f"{value:.1f}".replace(".", ",") + f" {units[index]}"


def read_gpu_details_list() -> list[dict]:
    """Читает сведения обо всех видеокартах NVIDIA.

    nvidia-smi печатает по строке на каждую карту. Результат недолго
    живёт в кеше: окно производительности опрашивает его из фона.
    """

    now = time.monotonic()
    cached = _GPU_DETAILS.get("values")

    if (
        isinstance(cached, list)
        and now - _GPU_DETAILS.get("time", 0.0) < _GPU_CACHE_SECONDS
    ):
        return [dict(item) for item in cached]

    result: list[dict] = []

    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu="
                "name,memory.used,memory.total,temperature.gpu,"
                "power.draw,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
            **hidden_process_options(),
        )

        for index, line in enumerate(
            (completed.stdout or "").strip().splitlines()
        ):
            parts = [part.strip() for part in line.split(",")]

            if len(parts) < 6:
                continue

            result.append(
                {
                    "index": index,
                    "name": parts[0] or f"GPU {index}",
                    "memory_used": _to_bytes(
                        parts[1],
                        1024 * 1024,
                    ),
                    "memory_total": _to_bytes(
                        parts[2],
                        1024 * 1024,
                    ),
                    "temperature": _to_float(parts[3]),
                    "power": _to_float(parts[4]),
                    "utilization": _to_float(parts[5]),
                }
            )
    except (OSError, subprocess.SubprocessError, ValueError):
        result = []

    _GPU_DETAILS["values"] = [dict(item) for item in result]
    _GPU_DETAILS["time"] = now
    _GPU_DETAILS["value"] = dict(result[0]) if result else {}

    return [dict(item) for item in result]


def read_gpu_details() -> dict:
    """Читает сведения об основной видеокарте (для совместимости)."""

    values = read_gpu_details_list()

    return dict(values[0]) if values else {}


_GPU_DETAILS: dict = {"value": None, "values": None, "time": 0.0}


def _to_float(text: str) -> float:
    """Переводит ответ nvidia-smi в число, терпя пустые значения."""

    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _to_bytes(text: str, factor: int) -> int:
    """Переводит MiB из ответа nvidia-smi в байты."""

    return int(round(_to_float(text) * factor))


def create_monitor():
    """Создаёт лучший доступный источник показателей."""

    if os.name == "nt":
        try:
            return WindowsCounters()
        except (OSError, AttributeError):
            pass

    try:
        return PsutilCounters()
    except ImportError:
        return None
