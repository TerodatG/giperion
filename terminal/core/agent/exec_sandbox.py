# Giperion/terminal/core/agent/exec_sandbox.py                        v001
# Запуск команд агента: чистое окружение, Job Objects, запрет egress.
# Последнее изменение: первый вариант — процесс и Python в AppContainer.

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from config import DATA_DIR
from terminal.core.agent import sandbox

MEMORY_MB = 1024
CPU_SECONDS = 60
DEAD_PROXY = "http://127.0.0.1:9"
TEMP_DIR = DATA_DIR / "agent_exec_tmp"


@dataclass(frozen=True)
class ExecResult:
    """Код, вывод и признак реальной изоляции."""

    code: int
    output: str
    timed_out: bool = False
    isolated: bool = False


def _temp_dir() -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    return TEMP_DIR


def env_for(root: Path) -> dict[str, str]:
    """Окружение команды: без секретов, с мёртвым прокси и git без промпта."""

    temp = _temp_dir()
    env = sandbox.plugin_env(Path(root), temp)
    env.update(
        {
            "HOME": str(temp),
            "USERPROFILE": str(temp),
            "TMP": str(temp),
            "TEMP": str(temp),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": str(temp / ".gitconfig"),
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "echo",
            "GIPERION_EGRESS": "deny",
            "NO_PROXY": "",
            "no_proxy": "",
        }
    )

    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        env[name] = DEAD_PROXY

    return env


def isolation() -> str:
    """Режим из настроек: process, auto или appcontainer."""

    try:
        from terminal.core.agent import settings

        return settings.command_sandbox()
    except Exception:  # noqa: BLE001 — без настроек обычный процесс
        return "process"


def _popen(args: list[str], cwd: Path) -> subprocess.Popen:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    return subprocess.Popen(
        args,
        cwd=str(Path(cwd).resolve()),
        env=env_for(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )


def run(
    args: list[str],
    cwd: Path,
    timeout: int = 300,
    memory_mb: int = MEMORY_MB,
    cpu_seconds: int = CPU_SECONDS,
) -> ExecResult:
    """Запускает процесс с лимитами и чистым окружением."""

    if not args:
        return ExecResult(1, "Пустая команда.")

    try:
        process = _popen(args, cwd)
    except OSError as error:
        return ExecResult(1, f"Не удалось запустить: {error}")

    job = sandbox.attach(
        process.pid,
        memory_mb=memory_mb,
        cpu_seconds=cpu_seconds,
    )

    try:
        stdout, stderr = process.communicate(timeout=max(1, timeout))
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()

        return ExecResult(
            -1,
            f"Команда не успела за {timeout} секунд.",
            timed_out=True,
            isolated=job is not None,
        )
    finally:
        sandbox.close(job)

    output = ((stdout or "") + (stderr or "")).strip()

    return ExecResult(
        int(process.returncode),
        output,
        isolated=job is not None,
    )


def run_python(
    args: list[str],
    cwd: Path,
    timeout: int = 300,
) -> ExecResult:
    """Python-команда: AppContainer, если он готов, иначе процесс."""

    mode = isolation()

    if mode not in ("auto", "appcontainer"):
        return run(args, cwd, timeout)

    try:
        from terminal.core.agent import container
    except Exception:  # noqa: BLE001 — Windows-only модуль
        if mode == "appcontainer":
            return ExecResult(1, "AppContainer недоступен на этой платформе.")

        return run(args, cwd, timeout)

    if not container.available():
        if mode == "appcontainer":
            return ExecResult(
                1,
                "AppContainer не подготовлен: "
                "python -m tools.setup_plugin_container --prepare",
            )

        return run(args, cwd, timeout)

    try:
        code, output = container.run_text(
            args[1:],
            cwd=Path(cwd),
            timeout=timeout,
            extra_env={
                "PYTEST_ADDOPTS": "-p no:cacheprovider",
                "GIPERION_EGRESS": "deny",
            },
        )
    except container.ContainerError as error:
        return ExecResult(1, str(error))

    return ExecResult(
        int(code),
        output.strip(),
        isolated=True,
    )


def is_python(args: list[str]) -> bool:
    """Первая команда — текущий Python."""

    if not args:
        return False

    try:
        return Path(args[0]).resolve() == Path(sys.executable).resolve()
    except (OSError, ValueError):
        return False
