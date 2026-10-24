# Giperion/app/core/system_info.py                                v001
# Основные параметры компьютера, на котором запущен Гиперион.
# Последнее изменение: первый вариант — ОС, ЦП, ОЗУ, GPU, диск, Python, PyTorch.

import ctypes
import os
import platform
import shutil
import socket
from pathlib import Path

from config import BASE_DIR

_CACHE: dict | None = None


def format_bytes(value: int | None) -> str:
    """Пишет размер в удобных единицах: ГБ, МБ и т.д."""

    if not value:
        return "—"

    size = float(value)
    units = ("Б", "КБ", "МБ", "ГБ", "ТБ")
    index = 0

    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1

    if index >= 3:
        return f"{size:.1f}".replace(".", ",") + f" {units[index]}"

    return f"{int(size)} {units[index]}"


def _memory_info() -> tuple[int, int]:
    """Возвращает полный и доступный объём ОЗУ в байтах."""

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
                return (
                    int(status.ullTotalPhys),
                    int(status.ullAvailPhys),
                )
        except (AttributeError, OSError):
            pass

    try:
        page = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        total = int(page) * int(pages)

        return (total, 0)
    except (AttributeError, OSError, ValueError):
        return (0, 0)


def _processor_name() -> str:
    """Возвращает понятное имя процессора, если система его отдаёт."""

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            ) as key:
                value, _ = winreg.QueryValueEx(
                    key,
                    "ProcessorNameString",
                )

                if isinstance(value, str) and value.strip():
                    return " ".join(value.split())
        except OSError:
            pass

    return (
        platform.processor()
        or os.environ.get("PROCESSOR_IDENTIFIER", "")
        or platform.machine()
        or "неизвестно"
    )


def _gpu_info() -> tuple[str, int]:
    """Возвращает имя видеокарты и объём её памяти."""

    try:
        import torch

        if not torch.cuda.is_available():
            return ("CUDA недоступна", 0)

        names = [
            torch.cuda.get_device_name(index)
            for index in range(torch.cuda.device_count())
        ]
        total_memory = sum(
            int(torch.cuda.get_device_properties(index).total_memory)
            for index in range(torch.cuda.device_count())
        )

        return (", ".join(names) or "видеокарта не определена", total_memory)
    except Exception as error:  # noqa: BLE001 — сведения не критичны
        return (f"не удалось определить ({error.__class__.__name__})", 0)


def _torch_versions() -> tuple[str, str]:
    """Возвращает версии PyTorch и CUDA."""

    try:
        import torch

        return (
            str(torch.__version__),
            str(torch.version.cuda or "—"),
        )
    except Exception:  # noqa: BLE001 — PyTorch может быть не установлен
        return ("не установлен", "—")


def get_system_info(force: bool = False) -> dict:
    """Собирает сведения о системе один раз за запуск приложения."""

    global _CACHE

    if _CACHE is not None and not force:
        return dict(_CACHE)

    ram_total, ram_available = _memory_info()
    gpu_name, gpu_memory = _gpu_info()
    torch_version, cuda_version = _torch_versions()

    try:
        disk = shutil.disk_usage(str(BASE_DIR))
        disk_total = int(disk.total)
        disk_free = int(disk.free)
    except OSError:
        disk_total = 0
        disk_free = 0

    processor = _processor_name()

    _CACHE = {
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "processor": processor,
        "cpu_cores": os.cpu_count() or 0,
        "ram_total": ram_total,
        "ram_available": ram_available,
        "gpu": gpu_name,
        "gpu_memory": gpu_memory,
        "disk_total": disk_total,
        "disk_free": disk_free,
        "disk_path": str(Path(BASE_DIR).anchor or BASE_DIR),
        "python": platform.python_version(),
        "torch": torch_version,
        "cuda": cuda_version,
        "project": str(BASE_DIR),
    }

    return dict(_CACHE)
