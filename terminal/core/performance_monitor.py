# Giperion/terminal/core/performance_monitor.py                    v003
# Живые показатели компьютера: ЦП, память, диски, сеть и видеокарты.
# Последнее изменение: чтение всех видеокарт NVIDIA.

import ctypes
import os
import re
import shutil
import subprocess
import time
from ctypes import wintypes as wt
from dataclasses import dataclass, field

from config import BASE_DIR
from shared.process_tools import hidden_process_options

# Имена экземпляров счётчиков ядер выглядят как «0,0», «0,1» и т.д.
_CORE_PATTERN = re.compile(r"^\d+,\d+$")

# Сетевые интерфейсы, которые не считаем реальным трафиком.
_GHOST_INTERFACES = ("loopback", "isatap", "teredo", "pseudo")

# Как часто перечитывать список томов и сведения видеокарты.
_VOLUME_CACHE_SECONDS = 30.0
_GPU_CACHE_SECONDS = 4.0

# Счётчики, которые нужны окну производительности.
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

# Счётчики, без которых окно всё равно работает.
_OPTIONAL_COUNTERS = (
    "cpu_frequency",
    "disk_queue",
    "gpu",
    "gpu_memory",
    "gpu_memory_total",
)


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


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Ограничивает показатель разумными рамками."""

    return max(low, min(high, float(value)))


def _sum_filtered(
    values: list[tuple[str, float]],
    contains: str = "",
) -> float:
    """Суммирует значения экземпляров, отбрасывая служебные."""

    total = 0.0

    for name, value in values:
        lowered = name.lower()

        if contains and contains not in lowered:
            continue

        if any(ghost in lowered for ghost in _GHOST_INTERFACES):
            continue

        total += value

    return total


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
