# Giperion/terminal/core/performance_types.py                         v001
# Общие типы и снимки производительности.
# Последнее изменение: вынесено из performance_monitor.

import ctypes
import os
import shutil
import time
from dataclasses import dataclass, field

from config import BASE_DIR

_VOLUME_CACHE_SECONDS = 30.0
_GPU_CACHE_SECONDS = 4.0

@dataclass
class VolumeUsage:
    """Занятое место на одном томе (диске C:, D: и т.д.)."""

    name: str
    total: int
    free: int


@dataclass
class PerformanceSample:
    """Один замер производительности, как снимок Диспетчера задач."""

    cpu_percent: float = 0.0
    cpu_cores: list[float] = field(default_factory=list)
    cpu_frequency_mhz: float = 0.0
    ram_total: int = 0
    ram_available: int = 0
    ram_percent: float = 0.0
    disk_percent: float = 0.0
    disk_queue: float = 0.0
    disk_read_bps: float = 0.0
    disk_write_bps: float = 0.0
    net_down_bps: float = 0.0
    net_up_bps: float = 0.0
    gpu_percent: float = 0.0
    gpu_memory_used: int = 0
    gpu_memory_total: int = 0
    volumes: list[VolumeUsage] = field(default_factory=list)
    uptime: float = 0.0
    source: str = ""


def _total_memory() -> int:
    """Возвращает полный объём ОЗУ в байтах."""

    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)

        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(status)
            ):
                return int(status.ullTotalPhys)
        except (AttributeError, OSError):
            pass

    try:
        page = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")

        return int(page) * int(pages)
    except (AttributeError, OSError, ValueError):
        return 0


def _uptime_seconds() -> float:
    """Возвращает время работы системы в секундах."""

    if os.name == "nt":
        try:
            return ctypes.windll.kernel32.GetTickCount64() / 1000.0
        except (AttributeError, OSError):
            pass

    try:
        clock_id = getattr(time, "CLOCK_BOOTTIME", None)

        if clock_id is not None:
            return time.clock_gettime(clock_id)
    except (AttributeError, OSError):
        pass

    return 0.0


def _volumes() -> list[VolumeUsage]:
    """Собирает список локальных томов и свободное место на них."""

    found: list[VolumeUsage] = []

    if os.name == "nt":
        mask = ctypes.windll.kernel32.GetLogicalDrives()

        for index in range(26):
            if not mask & (1 << index):
                continue

            letter = f"{chr(ord('A') + index)}:"
            root = f"{letter}\\"

            # Только постоянные тома: 3 — DRIVE_FIXED.
            if (
                ctypes.windll.kernel32.GetDriveTypeW(
                    ctypes.c_wchar_p(root)
                )
                != 3
            ):
                continue

            try:
                usage = shutil.disk_usage(root)
            except OSError:
                continue

            found.append(
                VolumeUsage(
                    name=letter,
                    total=int(usage.total),
                    free=int(usage.free),
                )
            )

        if found:
            return found

    try:
        usage = shutil.disk_usage(str(BASE_DIR))
        found.append(
            VolumeUsage(
                name=str(BASE_DIR)[:2] or "диск",
                total=int(usage.total),
                free=int(usage.free),
            )
        )
    except OSError:
        pass

    return found

