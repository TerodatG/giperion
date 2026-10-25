# Giperion/terminal/core/agent/sandbox.py                              v001
# Песочница процесса плагина: чистое окружение и лимиты Windows.
# Последнее изменение: первый вариант — env, рабочая папка, Job Objects.

import os
import sys
from pathlib import Path

MEMORY_MB = 512
CPU_SECONDS = 30

# Переменные, без которых не стартует Python и не работает система.
ENV_KEEP = {
    "PATH",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "TEMP",
    "TMP",
    "COMSPEC",
    "PATHEXT",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "PYTHONHOME",
}

# Слова в именах переменных, которые не должны попадать в плагин.
SENSITIVE = (
    "KEY",
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "AUTH",
    "PROXY",
    "COOKIE",
    "SESSION",
    "CREDENTIAL",
)

JOB_OBJECT_LIMIT_JOB_TIME = 0x0004
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x0100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x0200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001


def is_sensitive(name: str) -> bool:
    """Похоже ли имя переменной окружения на секрет."""

    upper = str(name or "").upper()

    return any(word in upper for word in SENSITIVE)


def plugin_env(base_dir: Path) -> dict[str, str]:
    """Окружение плагина: только системный минимум и путь к проекту."""

    env: dict[str, str] = {}

    for key, value in os.environ.items():
        if key.upper() in ENV_KEEP and not is_sensitive(key):
            env[key] = value

    env["PYTHONPATH"] = str(Path(base_dir).resolve())
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AGENT_PLUGIN_SANDBOX"] = "1"

    return env


def _structures():
    """Структуры WinAPI для Job Objects (только на Windows)."""

    import ctypes
    from ctypes import wintypes

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimits),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    return ctypes, wintypes, ExtendedLimits


def available() -> bool:
    """Есть ли в системе Job Objects (Windows)."""

    return sys.platform == "win32"


def attach(
    pid: int,
    memory_mb: int = MEMORY_MB,
    cpu_seconds: int = CPU_SECONDS,
):
    """Сажает процесс в job с лимитами памяти и CPU.

    Возвращает дескриптор job или None, если ограничения недоступны.
    """

    if not available() or sys.platform != "win32" or pid <= 0:
        return None

    try:
        ctypes, _wintypes, extended = _structures()
        kernel32 = ctypes.windll.kernel32
    except (AttributeError, OSError):
        return None

    job = kernel32.CreateJobObjectW(None, None)

    if not job:
        return None

    info = extended()
    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_PROCESS_MEMORY
        | JOB_OBJECT_LIMIT_JOB_MEMORY
        | JOB_OBJECT_LIMIT_JOB_TIME
        | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    info.BasicLimitInformation.PerJobUserTimeLimit = int(cpu_seconds) * 10_000_000
    info.ProcessMemoryLimit = int(memory_mb) * 1024 * 1024
    info.JobMemoryLimit = int(memory_mb) * 1024 * 1024

    configured = kernel32.SetInformationJobObject(
        job,
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )

    process = kernel32.OpenProcess(
        PROCESS_SET_QUOTA | PROCESS_TERMINATE,
        False,
        int(pid),
    )

    if not configured or not process:
        kernel32.CloseHandle(job)

        return None

    assigned = kernel32.AssignProcessToJobObject(job, process)
    kernel32.CloseHandle(process)

    if not assigned:
        kernel32.CloseHandle(job)

        return None

    return job


def close(job) -> None:
    """Закрывает job; процесс внутри при этом завершается."""

    if not job or sys.platform != "win32":
        return

    try:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(job)
    except (AttributeError, OSError):
        pass
