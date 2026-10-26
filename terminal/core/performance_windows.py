# Giperion/terminal/core/performance_windows.py                       v001
# Счётчики Windows через PDH: ядра, диск, сеть и видеокарта.
# Последнее изменение: вынесено из performance_monitor.

import ctypes
import re
import time
from ctypes import wintypes as wt

from terminal.core.performance_helpers import _clamp, _sum_filtered
from terminal.core.performance_types import (
    _VOLUME_CACHE_SECONDS,
    PerformanceSample,
    VolumeUsage,
    _total_memory,
    _uptime_seconds,
    _volumes,
)

_CORE_PATTERN = re.compile(r"^\d+,\d+$")
_COUNTERS = {
    "cpu_cores": r"\Processor Information(*)\% Processor Utility",
    "cpu_frequency": r"\Processor Information(_Total)\Processor Frequency",
    "ram_available": r"\Memory\Available MBytes",
    "disk_idle": r"\PhysicalDisk(_Total)\% Idle Time",
    "disk_queue": r"\PhysicalDisk(_Total)\Current Disk Queue Length",
    "disk_read": r"\PhysicalDisk(_Total)\Disk Read Bytes/sec",
    "disk_write": r"\PhysicalDisk(_Total)\Disk Write Bytes/sec",
    "net_down": r"\Network Interface(*)\Bytes Received/sec",
    "net_up": r"\Network Interface(*)\Bytes Sent/sec",
    "gpu": r"\GPU Engine(*)\Utilization Percentage",
    "gpu_memory": r"\GPU Adapter Memory(*)\Dedicated Usage",
    "gpu_memory_total": r"\GPU Adapter Memory(*)\Dedicated Limit",
}
_OPTIONAL_COUNTERS = (
    "cpu_frequency",
    "disk_queue",
    "gpu",
    "gpu_memory",
    "gpu_memory_total",
)


class _PdhValue(ctypes.Structure):
    """Значение счётчика: структура PDH_FMT_COUNTERVALUE из winpdh.h."""

    class _Union(ctypes.Union):
        _fields_ = [
            ("longValue", wt.LONG),
            ("doubleValue", ctypes.c_double),
            ("largeValue", ctypes.c_longlong),
            ("AnsiStringValue", ctypes.c_char_p),
            ("WideStringValue", ctypes.c_wchar_p),
        ]

    _anonymous_ = ("value",)
    _fields_ = [
        ("CStatus", wt.DWORD),
        ("value", _Union),
    ]


class _PdhItem(ctypes.Structure):
    """Элемент массива значений (PDH_FMT_COUNTERVALUE_ITEM_W)."""

    _fields_ = [
        ("szName", wt.LPWSTR),
        ("FmtValue", _PdhValue),
    ]


class WindowsCounters:
    """Счётчики производительности Windows через PDH.

    Диспетчер задач берёт цифры отсюда же. Английские имена счётчиков
    работают и на русской системе, поэтому локаль не мешает.
    """

    PDH_FMT_DOUBLE = 0x00000200
    PDH_MORE_DATA = 0x800007D2
    PDH_CSTATUS_VALID_DATA = 0x00000000

    def __init__(self) -> None:
        self._pdh = ctypes.WinDLL("pdh.dll")
        self._query = wt.HANDLE()
        self._handles: dict[str, wt.HANDLE] = {}
        self._missing: set[str] = set()

        self._bind_api()

        status = self._pdh.PdhOpenQueryW(
            None,
            0,
            ctypes.byref(self._query),
        )

        if status != 0:
            raise OSError(f"PDH: не удалось открыть запрос (0x{status:08X})")

        for key, path in _COUNTERS.items():
            self._add(key, path)

        # Сеть, видеокарта и ядра читаются массивами экземпляров.
        self._wildcard = {
            "cpu_cores": True,
            "net_down": True,
            "net_up": True,
            "gpu": True,
            "gpu_memory": True,
            "gpu_memory_total": True,
        }

        self._ram_total = _total_memory()
        self._volumes: list[VolumeUsage] = []
        self._volumes_time = -_VOLUME_CACHE_SECONDS

        # Первый сбор запускает счётчики: значения появятся со второго.
        self._pdh.PdhCollectQueryData(self._query)

    def _bind_api(self) -> None:
        """Задаёт типы аргументов, чтобы указатели не обрезались."""

        self._pdh.PdhAddEnglishCounterW.argtypes = [
            wt.HANDLE,
            wt.LPCWSTR,
            ctypes.c_size_t,
            ctypes.POINTER(wt.HANDLE),
        ]
        self._pdh.PdhAddEnglishCounterW.restype = wt.LONG

        self._pdh.PdhCollectQueryData.argtypes = [wt.HANDLE]
        self._pdh.PdhCollectQueryData.restype = wt.LONG

        self._pdh.PdhGetFormattedCounterValue.argtypes = [
            wt.HANDLE,
            wt.DWORD,
            ctypes.POINTER(wt.DWORD),
            ctypes.POINTER(_PdhValue),
        ]
        self._pdh.PdhGetFormattedCounterValue.restype = wt.LONG

        self._pdh.PdhGetFormattedCounterArrayW.argtypes = [
            wt.HANDLE,
            wt.DWORD,
            ctypes.POINTER(wt.DWORD),
            ctypes.POINTER(wt.DWORD),
            ctypes.POINTER(_PdhItem),
        ]
        self._pdh.PdhGetFormattedCounterArrayW.restype = wt.LONG

    def _add(self, key: str, path: str) -> None:
        """Добавляет счётчик в запрос, если система его знает."""

        handle = wt.HANDLE()
        status = self._pdh.PdhAddEnglishCounterW(
            self._query,
            path,
            0,
            ctypes.byref(handle),
        )

        if status != 0:
            if key in _OPTIONAL_COUNTERS:
                self._missing.add(key)

                return

            raise OSError(
                f"PDH: счётчик недоступен: {path} (0x{status:08X})"
            )

        self._handles[key] = handle

    # --- Чтение значений ---

    def _value(self, key: str) -> float | None:
        """Возвращает один показатель или None, если его нет."""

        handle = self._handles.get(key)

        if handle is None:
            return None

        value = _PdhValue()
        status = self._pdh.PdhGetFormattedCounterValue(
            handle,
            self.PDH_FMT_DOUBLE,
            None,
            ctypes.byref(value),
        )

        if (
            status & 0xFFFFFFFF
        ) != 0 or value.CStatus != self.PDH_CSTATUS_VALID_DATA:
            return None

        return float(value.doubleValue)

    def _array(self, key: str) -> list[tuple[str, float]]:
        """Возвращает значения всех экземпляров счётчика."""

        handle = self._handles.get(key)

        if handle is None:
            return []

        size = wt.DWORD(0)
        count = wt.DWORD(0)

        status = self._pdh.PdhGetFormattedCounterArrayW(
            handle,
            self.PDH_FMT_DOUBLE,
            ctypes.byref(size),
            ctypes.byref(count),
            None,
        )

        # PDH_STATUS знаковый: код «нужен буфер» сравниваем по маске.
        if (
            status & 0xFFFFFFFF
        ) != self.PDH_MORE_DATA or size.value == 0:
            return []

        buffer = ctypes.create_string_buffer(size.value)

        status = self._pdh.PdhGetFormattedCounterArrayW(
            handle,
            self.PDH_FMT_DOUBLE,
            ctypes.byref(size),
            ctypes.byref(count),
            ctypes.cast(buffer, ctypes.POINTER(_PdhItem)),
        )

        if (status & 0xFFFFFFFF) != 0:
            return []

        items = ctypes.cast(
            buffer,
            ctypes.POINTER(_PdhItem),
        )

        values: list[tuple[str, float]] = []

        for index in range(count.value):
            item = items[index]
            name = item.szName or ""

            if item.FmtValue.CStatus != self.PDH_CSTATUS_VALID_DATA:
                continue

            values.append((name, float(item.FmtValue.doubleValue)))

        return values

    # --- Замер ---

    def _current_volumes(self) -> list[VolumeUsage]:
        """Отдаёт список томов, обновляя его не чаще раза в полминуты."""

        now = time.monotonic()

        if now - self._volumes_time >= _VOLUME_CACHE_SECONDS:
            self._volumes = _volumes()
            self._volumes_time = now

        return list(self._volumes)

    def sample(self) -> PerformanceSample:
        """Снимает один снимок производительности."""

        self._pdh.PdhCollectQueryData(self._query)

        sample = PerformanceSample(
            ram_total=self._ram_total,
            uptime=_uptime_seconds(),
            source="счётчики Windows",
        )

        # Процессор: общая загрузка и отдельные ядра.
        cores = [
            (name, value)
            for name, value in self._array("cpu_cores")
            if _CORE_PATTERN.match(name)
        ]

        total = dict(self._array("cpu_cores")).get("_Total")

        if total is not None:
            sample.cpu_percent = _clamp(total)

        sample.cpu_cores = [_clamp(value) for _, value in cores]

        if not sample.cpu_percent and cores:
            sample.cpu_percent = _clamp(
                sum(value for _, value in cores) / len(cores)
            )

        frequency = self._value("cpu_frequency")

        if frequency:
            sample.cpu_frequency_mhz = frequency

        # Память.
        available_mb = self._value("ram_available")

        if available_mb is not None:
            sample.ram_available = int(available_mb * 1024 * 1024)

        if sample.ram_total:
            sample.ram_percent = _clamp(
                (sample.ram_total - sample.ram_available)
                / sample.ram_total
                * 100.0
            )

        # Диски: занятость и скорость обмена.
        idle = self._value("disk_idle")

        if idle is not None:
            sample.disk_percent = _clamp(100.0 - idle)

        sample.disk_queue = max(0.0, self._value("disk_queue") or 0.0)
        sample.disk_read_bps = max(0.0, self._value("disk_read") or 0.0)
        sample.disk_write_bps = max(0.0, self._value("disk_write") or 0.0)

        # Сеть: сумма по реальным интерфейсам.
        sample.net_down_bps = _sum_filtered(self._array("net_down"))
        sample.net_up_bps = _sum_filtered(self._array("net_up"))

        # Видеокарта: занятость 3D-движка и выделенная память.
        sample.gpu_percent = _sum_filtered(
            self._array("gpu"),
            contains="engtype_3d",
        )
        sample.gpu_memory_used = int(
            _sum_filtered(self._array("gpu_memory"))
        )
        sample.gpu_memory_total = int(
            _sum_filtered(self._array("gpu_memory_total"))
        )

        sample.volumes = self._current_volumes()

        return sample

    def close(self) -> None:
        """Закрывает запрос счётчиков."""

        if self._query:
            try:
                self._pdh.PdhCloseQuery(self._query)
            except (AttributeError, OSError):
                pass

            self._query = wt.HANDLE()

