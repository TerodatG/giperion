# Giperion/terminal/core/agent/container.py                           v001
# AppContainer для плагинов: копия Python, ACL, запуск процесса.
# Последнее изменение: прототип проверен на Windows 11, build 26300.

import ctypes
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

try:  # ctypes.wintypes есть не на всех платформах
    from ctypes import wintypes
except (ImportError, ValueError):  # pragma: no cover - не-Windows
    wintypes = None

from config import BASE_DIR, DATA_DIR
from terminal.core.agent import sandbox

PROFILE_NAME = "Giperion.Agent.Plugin"
COMMAND_PROFILE = "Giperion.Agent.Command"
PYTHON_DIR = DATA_DIR / "plugin_python"
MARKER = PYTHON_DIR / ".ready"
TEMP_DIR = BASE_DIR / ".agent_plugin_tmp"
WRITE_ROOT = DATA_DIR / "agent_plugin_out"
OUTPUT_PREFIX = "container_out_"
PLUGIN_OUT_ENV = "AGENT_PLUGIN_OUT"

PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001

SKIP_COPY = shutil.ignore_patterns(
    "site-packages",
    "__pycache__",
    "*.pyc",
    "test",
    "tests",
    "idlelib",
    "tkinter",
    "turtledemo",
    "ensurepip",
    "distutils",
    "lib2to3",
    "pydoc_data",
)

READ_DIRS = ("terminal", "shared", "model", "docs", "tests", "tools")
COMMAND_READ_DIRS = (
    "terminal",
    "shared",
    "docs",
    "tests",
    "tools",
    "knowledge",
    "model",
    "skins",
    ".git",
)
SKIP_DIRS = {".git", ".agent_worktrees", "models", "data"}
_COMMAND_GRANTED: set[str] = set()


class ContainerError(RuntimeError):
    """Контейнер недоступен или подготовка не удалась."""


def available() -> bool:
    """Готова ли копия Python и профиль контейнера."""

    return (
        sys.platform == "win32"
        and MARKER.is_file()
        and python_exe().is_file()
    )


def python_exe() -> Path:
    """Python внутри песочницы."""

    return PYTHON_DIR / "python.exe"


def plugin_write_dir(plugin_name: str) -> Path:
    """Папка, куда плагину разрешено писать в контейнере."""

    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(plugin_name or "")).strip("._")
    folder = WRITE_ROOT / (safe or "plugin")
    folder.mkdir(parents=True, exist_ok=True)

    return folder


def grant_write_scope(folder: Path) -> bool:
    """Выдаёт контейнеру запись в конкретную папку плагина."""

    try:
        _sid, sid_text = ensure_profile()
    except ContainerError:
        return False

    # Нужен проход по родительской папке agent_plugin_out.
    _icacls(folder.parent, "/grant", f"*{sid_text}:RX", "/Q")

    return _icacls(
        folder,
        "/grant",
        f"*{sid_text}:(OI)(CI)M",
        "/T",
        "/Q",
    )


def _structures():
    import ctypes
    from ctypes import wintypes as wt

    class StartupInfoW(ctypes.Structure):
        _fields_ = [
            ("cb", wt.DWORD),
            ("lpReserved", wt.LPWSTR),
            ("lpDesktop", wt.LPWSTR),
            ("lpTitle", wt.LPWSTR),
            ("dwX", wt.DWORD),
            ("dwY", wt.DWORD),
            ("dwXSize", wt.DWORD),
            ("dwYSize", wt.DWORD),
            ("dwXCountChars", wt.DWORD),
            ("dwYCountChars", wt.DWORD),
            ("dwFillAttribute", wt.DWORD),
            ("dwFlags", wt.DWORD),
            ("wShowWindow", wt.WORD),
            ("cbReserved2", wt.WORD),
            ("lpReserved2", ctypes.c_void_p),
            ("hStdInput", wt.HANDLE),
            ("hStdOutput", wt.HANDLE),
            ("hStdError", wt.HANDLE),
        ]

    class StartupInfoEx(ctypes.Structure):
        _fields_ = [
            ("StartupInfo", StartupInfoW),
            ("lpAttributeList", ctypes.c_void_p),
        ]

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wt.DWORD)]

    class SecurityCapabilities(ctypes.Structure):
        _fields_ = [
            ("AppContainerSid", ctypes.c_void_p),
            ("Capabilities", ctypes.POINTER(SidAndAttributes)),
            ("CapabilityCount", wt.DWORD),
            ("Reserved", wt.DWORD),
        ]

    class ProcessInformation(ctypes.Structure):
        _fields_ = [
            ("hProcess", wt.HANDLE),
            ("hThread", wt.HANDLE),
            ("dwProcessId", wt.DWORD),
            ("dwThreadId", wt.DWORD),
        ]

    return (
        ctypes,
        StartupInfoEx,
        SecurityCapabilities,
        SidAndAttributes,
        ProcessInformation,
    )


def ensure_profile(profile: str = PROFILE_NAME):
    """Создаёт профиль AppContainer (или берёт существующий SID)."""

    if sys.platform != "win32":
        raise ContainerError("AppContainer доступен только на Windows.")

    name = str(profile or PROFILE_NAME)
    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    sid = ctypes.c_void_p()
    hr = userenv.CreateAppContainerProfile(
        name,
        name,
        "Изоляция агента Giperion",
        None,
        0,
        ctypes.byref(sid),
    )

    if (hr & 0xFFFFFFFF) == 0x800700B7:
        sid = ctypes.c_void_p()
        hr = userenv.DeriveAppContainerSidFromAppContainerName(
            name,
            ctypes.byref(sid),
        )

    if not sid:
        raise ContainerError(
            "Не удалось создать профиль AppContainer: "
            f"{hex(hr & 0xFFFFFFFF)}"
        )

    text = ctypes.c_void_p()
    advapi32.ConvertSidToStringSidW(sid, ctypes.byref(text))

    if not text:
        raise ContainerError("Не удалось получить строку SID контейнера.")

    value = ctypes.wstring_at(text.value)
    kernel32.LocalFree(text)

    return sid, value


def _icacls(path: Path, *args: str) -> bool:
    result = subprocess.run(
        ["icacls", str(path), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    return result.returncode == 0


def grant(
    sid_text: str,
    root: Path | None = None,
    dirs: tuple[str, ...] = READ_DIRS,
) -> list[str]:
    """Выдаёт контейнеру чтение проекта и запись во временную папку."""

    base = Path(root or BASE_DIR).resolve()
    report = []

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if _icacls(TEMP_DIR, "/grant", f"*{sid_text}:(OI)(CI)M", "/T", "/Q"):
        report.append(f"запись: {TEMP_DIR}")

    if _icacls(base, "/grant", f"*{sid_text}:RX", "/Q"):
        report.append("проход: корень проекта")

    if _icacls(base, "/grant", f"*{sid_text}:(OI)RX", "/Q"):
        report.append("чтение: файлы корня")

    for name in dirs:
        folder = base / name

        if not folder.is_dir():
            continue

        if _icacls(folder, "/grant", f"*{sid_text}:(OI)(CI)RX", "/T", "/Q"):
            report.append(f"чтение: {name}")

    tools_dir = base / "data" / "agent_tools"

    if tools_dir.is_dir() and _icacls(
        tools_dir, "/grant", f"*{sid_text}:(OI)(CI)RX", "/T", "/Q"
    ):
        report.append("чтение: data/agent_tools")

    # Копия Python лежит внутри data, поэтому контейнеру нужен проход
    # по самой папке data и чтение только своей копии.
    if PYTHON_DIR.is_dir():
        if _icacls(
            PYTHON_DIR.parent, "/grant", f"*{sid_text}:RX", "/Q"
        ):
            report.append("проход: data")

        if _icacls(
            PYTHON_DIR, "/grant", f"*{sid_text}:(OI)(CI)RX", "/T", "/Q"
        ):
            report.append(f"чтение: {PYTHON_DIR.name}")

    return report


def grant_commands(root: Path, git_exe: Path | None = None) -> bool:
    """Готовит командный профиль: проект на чтение, git и temp."""

    base = Path(root or BASE_DIR).resolve()
    key = str(base)

    if key in _COMMAND_GRANTED:
        return True

    _sid, sid_text = ensure_profile(COMMAND_PROFILE)
    grant(sid_text, base, COMMAND_READ_DIRS)

    if git_exe is not None:
        folder = Path(git_exe).resolve().parent

        while folder.parent != folder and folder.name.lower() not in (
            "git",
            "program files",
            "program files (x86)",
        ):
            folder = folder.parent

        _icacls(folder, "/grant", f"*{sid_text}:(OI)(CI)RX", "/T", "/Q")

    _COMMAND_GRANTED.add(key)

    return True


def revoke(sid_text: str, root: Path | None = None) -> list[str]:
    """Снимает выданные права."""

    base = Path(root or BASE_DIR).resolve()
    report = []

    for folder in [TEMP_DIR, base] + [
        base / name for name in READ_DIRS
    ]:
        if not folder.exists():
            continue

        if _icacls(folder, "/remove", f"*{sid_text}", "/T", "/Q"):
            report.append(str(folder))

    return report


def prepare(force: bool = False, source: Path | None = None) -> list[str]:
    """Копирует Python, выдаёт права и проверяет запуск."""

    steps: list[str] = []

    if sys.platform != "win32":
        raise ContainerError("AppContainer доступен только на Windows.")

    marker_text = MARKER.read_text(encoding="utf-8").strip() if MARKER.exists() else ""
    wanted = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    if force or marker_text != wanted or not python_exe().is_file():
        if PYTHON_DIR.exists():
            shutil.rmtree(PYTHON_DIR, ignore_errors=True)

        shutil.copytree(
            Path(source or sys.base_prefix),
            PYTHON_DIR,
            ignore=SKIP_COPY,
            dirs_exist_ok=True,
        )
        MARKER.parent.mkdir(parents=True, exist_ok=True)
        MARKER.write_text(wanted, encoding="utf-8")
        steps.append(f"скопирован Python {wanted}")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    _sid, sid_text = ensure_profile()
    steps.extend(grant(sid_text))

    code, output = run_text(
        ["-c", "print('container-ok')"],
        cwd=BASE_DIR,
    )

    if code != 0 or "container-ok" not in output:
        raise ContainerError(
            "Python в контейнере не запустился: "
            f"код {code}, вывод {output[:300]!r}"
        )

    steps.append("проверка: container-ok")

    return steps


def remove() -> list[str]:
    """Удаляет профиль контейнера, копию Python и права."""

    steps: list[str] = []

    if sys.platform == "win32":
        try:
            _sid, sid_text = ensure_profile()
            steps.extend(revoke(sid_text))
        except ContainerError:
            pass

        userenv = ctypes.WinDLL("userenv", use_last_error=True)
        hr = userenv.DeleteAppContainerProfile(PROFILE_NAME)

        if (hr & 0xFFFFFFFF) == 0:
            steps.append("профиль удалён")

    if PYTHON_DIR.exists():
        shutil.rmtree(PYTHON_DIR, ignore_errors=True)
        steps.append("копия Python удалена")

    return steps


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Окружение контейнера: родительское без секретов плюс правки."""

    env = {
        key: value
        for key, value in os.environ.items()
        if value is not None and not sandbox.is_sensitive(key)
    }
    env.update(
        {
            "PYTHONPATH": str(Path(BASE_DIR).resolve()),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "AGENT_PLUGIN_SANDBOX": "appcontainer",
            "TEMP": str(TEMP_DIR),
            "TMP": str(TEMP_DIR),
        }
    )

    if extra:
        env.update(extra)

    return env


def run_text(
    args: list[str],
    cwd: Path,
    timeout: int = 30,
    extra_env: dict[str, str] | None = None,
    executable: Path | None = None,
    profile: str = PROFILE_NAME,
) -> tuple[int, str]:
    """Запускает команду в контейнере и возвращает код и вывод."""

    if not available():
        raise ContainerError(
            "Песочница AppContainer не подготовлена: "
            "запусти python -m tools.setup_plugin_container --prepare."
        )

    (
        ctypes_mod,
        StartupInfoEx,
        SecurityCapabilities,
        SidAndAttributes,
        ProcessInformation,
    ) = _structures()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    sid, _sid_text = ensure_profile(profile)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    out_path = TEMP_DIR / f"{OUTPUT_PREFIX}{uuid.uuid4().hex}.txt"
    out = open(out_path, "wb")

    import msvcrt

    handle = wintypes.HANDLE(msvcrt.get_osfhandle(out.fileno()))
    os.set_handle_inheritable(int(handle.value), True)

    size = ctypes_mod.c_size_t(0)
    kernel32.InitializeProcThreadAttributeList(
        None, 1, 0, ctypes_mod.byref(size)
    )
    buffer = ctypes_mod.create_string_buffer(size.value)
    attr_list = ctypes_mod.cast(buffer, ctypes_mod.c_void_p)
    kernel32.InitializeProcThreadAttributeList(
        attr_list, 1, 0, ctypes_mod.byref(size)
    )

    caps = SecurityCapabilities()
    caps.AppContainerSid = sid
    caps.Capabilities = ctypes_mod.POINTER(SidAndAttributes)()
    caps.CapabilityCount = 0
    caps.Reserved = 0

    kernel32.UpdateProcThreadAttribute(
        attr_list,
        0,
        0x00020009,
        ctypes_mod.byref(caps),
        ctypes_mod.sizeof(caps),
        None,
        None,
    )

    si = StartupInfoEx()
    si.StartupInfo.cb = ctypes_mod.sizeof(StartupInfoEx)
    si.StartupInfo.dwFlags = 0x00000100
    si.StartupInfo.hStdInput = None
    si.StartupInfo.hStdOutput = handle
    si.StartupInfo.hStdError = handle
    si.lpAttributeList = attr_list

    pi = ProcessInformation()

    exe = Path(executable or python_exe())
    quoted = subprocess.list2cmdline([str(exe), *args])
    command = ctypes_mod.create_unicode_buffer(quoted)

    env = child_env(extra_env)
    block_text = "\0".join(
        f"{key}={value}" for key, value in sorted(env.items())
    ) + "\0\0"
    block = ctypes_mod.create_unicode_buffer(block_text)

    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes_mod.c_void_p,
        ctypes_mod.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes_mod.c_void_p,
        wintypes.LPCWSTR,
        ctypes_mod.c_void_p,
        ctypes_mod.c_void_p,
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL

    created = kernel32.CreateProcessW(
        None,
        command,
        None,
        None,
        True,
        0x00080000 | 0x00000400,
        ctypes_mod.cast(block, ctypes_mod.c_void_p),
        str(Path(cwd).resolve()),
        ctypes_mod.byref(si),
        ctypes_mod.byref(pi),
    )

    if not created:
        error = ctypes.get_last_error()
        out.close()
        out_path.unlink(missing_ok=True)

        raise ContainerError(
            f"CreateProcess в контейнере не удался: код {error}"
        )

    job = sandbox.attach(pi.dwProcessId)

    try:
        waited = kernel32.WaitForSingleObject(
            pi.hProcess,
            max(1, int(timeout)) * 1000,
        )

        if waited != 0:
            kernel32.TerminateProcess(pi.hProcess, 1)

        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(pi.hProcess, ctypes_mod.byref(code))
    finally:
        kernel32.CloseHandle(pi.hProcess)
        kernel32.CloseHandle(pi.hThread)
        sandbox.close(job)
        out.close()

    try:
        output = out_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        output = ""

    out_path.unlink(missing_ok=True)

    if waited != 0:
        return -1, f"Контейнер не успел за {timeout} с. {output[:200]}"

    return int(code.value), output


def status() -> dict:
    """Состояние песочницы для окна и CLI."""

    ready = available()

    return {
        "ready": ready,
        "platform": sys.platform,
        "python": str(python_exe()),
        "profile": PROFILE_NAME,
        "temp": str(TEMP_DIR),
    }
