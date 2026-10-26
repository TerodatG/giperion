# Giperion/terminal/core/agent/plugin_runner.py                      v001
# Дочерний процесс для плагина: загрузка, вызов и JSON-ответ.
# Последнее изменение: изоляция плагинов от процесса Терминала.

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

from config import BASE_DIR
from terminal.core.agent import sandbox
from terminal.core.agent.protocol import ToolResult

TIMEOUT = 30
MAX_OUTPUT = 10_000
EXIT_QUOTA = 0xC0000044


def _exit_hint(code: int) -> str:
    """Подсказка по коду завершения процесса плагина."""

    if code == EXIT_QUOTA:
        return "Плагин превысил лимит времени CPU и был остановлен."

    return ""


def _allowed_roots(root: Path, module_dir: Path | None) -> tuple[list[Path], list[Path]]:
    """Корни для чтения и записи."""

    allowed_read = [
        Path(root).resolve(),
        Path(BASE_DIR).resolve(),
        Path(sys.base_prefix).resolve(),
        Path(sys.prefix).resolve(),
    ]

    if module_dir is not None:
        allowed_read.append(Path(module_dir).resolve())

    allowed_write = [Path(root).resolve()]
    container_temp = os.environ.get("TEMP") or os.environ.get("TMP")

    if container_temp:
        try:
            allowed_write.append(Path(container_temp).resolve())
        except (OSError, ValueError):
            pass

    plugin_out = os.environ.get("AGENT_PLUGIN_OUT")

    if plugin_out:
        try:
            folder = Path(plugin_out).resolve()
            allowed_write.append(folder)
            allowed_read.append(folder)
        except (OSError, ValueError):
            pass

    return allowed_read, allowed_write


def _inside(path, roots: list[Path]) -> bool:
    """Лежит ли путь внутри одного из корней."""

    try:
        real = Path(os.path.realpath(str(path))).resolve()
    except (OSError, ValueError, TypeError):
        return False

    return any(real == base or base in real.parents for base in roots)


def _deny(what: str, path: str = "") -> None:
    """Отказывает в доступе с понятным текстом."""

    detail = f" ({path})" if path else ""

    raise PermissionError(f"Песочница плагина: {what}{detail}")


def _check_open(args, allowed_read, allowed_write) -> None:
    """Проверяет открытие файла."""

    path = args[0] if args else None

    if path is None or isinstance(path, int):
        return

    mode = str(args[1] or "") if len(args) > 1 else ""
    writing = any(symbol in mode for symbol in "wax+")

    if writing:
        if not _inside(path, allowed_write):
            _deny("запись за пределами проекта", str(path))
    elif not _inside(path, allowed_read):
        _deny("чтение за пределами проекта", str(path))


def _check_mutation(args, allowed_write) -> None:
    """Проверяет изменения файлов и папок."""

    for path in args:
        if isinstance(path, (str, bytes, os.PathLike)) and path:
            if not _inside(path, allowed_write):
                _deny("изменение за пределами проекта", str(path))


def install_guard(
    root: Path,
    permissions: tuple[str, ...] = (),
    module_dir: Path | None = None,
) -> None:
    """Ставит сторож на файлы, сеть и запуск программ.

    Это не песочница уровня ОС: ctypes и прямые вызовы WinAPI теоретически
    обходят аудит-хук. Но случайный или честный плагин уже не откроет
    файл за пределами проекта, не полезет в сеть и не запустит процесс
    без разрешения.
    """

    allowed_read, allowed_write = _allowed_roots(root, module_dir)
    allow_net = "net" in permissions
    allow_exec = "exec" in permissions

    mutation_events = {
        "os.mkdir",
        "os.rmdir",
        "os.remove",
        "os.rename",
        "os.replace",
        "os.symlink",
        "os.link",
        "os.truncate",
    }
    exec_events = {
        "subprocess.Popen",
        "os.system",
        "os.exec",
        "os.spawn",
        "os.posix_spawn",
    }

    def hook(event: str, args: tuple) -> None:
        if event == "open":
            _check_open(args, allowed_read, allowed_write)
        elif event in mutation_events:
            _check_mutation(args, allowed_write)
        elif event.startswith("socket.") and not allow_net:
            _deny("сеть запрещена")
        elif event in exec_events and not allow_exec:
            _deny("запуск программ запрещён")

    sys.addaudithook(hook)


def _load_module(path: Path, handler_name: str):
    """Загружает модуль плагина в этом процессе."""

    module_name = f"agent_plugin_process_{path.stem}"

    spec = importlib.util.spec_from_file_location(module_name, path)

    if spec is None or spec.loader is None:
        raise RuntimeError("Не удалось загрузить модуль плагина.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    tool = getattr(module, "TOOL", None)
    handler = None

    if isinstance(tool, dict):
        handler = tool.get("handler")

    if handler is None:
        handler = getattr(module, handler_name, None)

    if not callable(handler):
        raise RuntimeError("В плагине нет обработчика.")

    return handler


def execute_plugin(
    module_path: Path,
    root: Path,
    args: dict,
    handler_name: str = "handler",
    permissions: tuple[str, ...] = (),
) -> ToolResult:
    """Выполняет плагин и возвращает результат."""

    install_guard(root, permissions, Path(module_path).parent)

    handler = _load_module(module_path, handler_name)

    captured = io.StringIO()

    try:
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(
            captured
        ):
            result = handler(Path(root), args)
    except Exception as error:  # noqa: BLE001 — ошибку увидит агент
        return ToolResult(
            False,
            f"Плагин упал: {type(error).__name__}: {error}",
        )

    if isinstance(result, ToolResult):
        return result

    if (
        isinstance(result, (tuple, list))
        and len(result) == 2
        and isinstance(result[1], str)
    ):
        return ToolResult(bool(result[0]), result[1])

    return ToolResult(
        False,
        "Плагин вернул не ToolResult.",
    )


def run_plugin_process(
    module_path: Path,
    root: Path,
    args: dict,
    handler_name: str = "handler",
    timeout: int = TIMEOUT,
    memory_mb: int | None = None,
    cpu_seconds: int | None = None,
    permissions: tuple[str, ...] = (),
) -> ToolResult:
    """Запускает плагин в отдельном процессе с песочницей."""

    command = [
        sys.executable,
        "-m",
        "terminal.core.agent.plugin_runner",
        str(module_path),
        str(root),
        json.dumps(args, ensure_ascii=False),
        handler_name,
        json.dumps(list(permissions), ensure_ascii=False),
    ]

    mode = _sandbox_mode()

    if mode == "appcontainer":
        return _run_in_container(
            module_path,
            root,
            args,
            handler_name,
            timeout,
            permissions,
        )

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    temp_dir = Path(root).resolve() / ".agent_plugin_tmp"

    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        temp_dir = Path(root).resolve()

    env = sandbox.plugin_env(BASE_DIR, temp_dir)

    try:
        process = subprocess.Popen(
            command,
            cwd=str(Path(root).resolve()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
    except OSError as error:
        return ToolResult(False, f"Плагин не запустился: {error}")

    job = sandbox.attach(
        process.pid,
        memory_mb=memory_mb or sandbox.MEMORY_MB,
        cpu_seconds=cpu_seconds or sandbox.CPU_SECONDS,
    )

    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()

        return ToolResult(
            False,
            f"Плагин не успел за {timeout} секунд и был остановлен.",
        )
    finally:
        sandbox.close(job)

    output = (stdout or "").strip()

    return _parse_output(output, process.returncode)


def _sandbox_mode() -> str:
    """Режим изоляции из настроек."""

    try:
        from terminal.core.agent import settings

        return settings.plugin_sandbox()
    except Exception:  # noqa: BLE001 — без настроек обычный процесс
        return "process"


def _parse_output(output: str, code: int) -> ToolResult:
    """Разбирает JSON-ответ дочернего процесса."""

    lines = [line for line in str(output).splitlines() if line.strip()]

    if not lines:
        hint = _exit_hint(code)

        if hint:
            return ToolResult(False, hint)

        return ToolResult(
            False,
            f"Плагин завершился без ответа (код {code}).",
        )

    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return ToolResult(
            False,
            "Плагин вернул не JSON: " + str(output)[-400:],
        )

    if not isinstance(payload, dict):
        return ToolResult(False, "Плагин вернул не объект.")

    return ToolResult(
        bool(payload.get("ok")),
        str(payload.get("text") or "")[:MAX_OUTPUT],
    )


def _run_in_container(
    module_path: Path,
    root: Path,
    args: dict,
    handler_name: str,
    timeout: int,
    permissions: tuple[str, ...],
) -> ToolResult:
    """Запускает плагин в AppContainer с копией Python."""

    try:
        from terminal.core.agent import container
    except Exception as error:  # noqa: BLE001 — Windows-only модуль
        return ToolResult(
            False,
            f"Песочница AppContainer недоступна: {error}",
        )

    if not container.available():
        return ToolResult(
            False,
            "Песочница AppContainer не подготовлена. Запусти "
            "python -m tools.setup_plugin_container --prepare "
            "или переключи режим в «Провайдере».",
        )

    command_args = [
        "-m",
        "terminal.core.agent.plugin_runner",
        str(module_path),
        str(root),
        json.dumps(args, ensure_ascii=False),
        handler_name,
        json.dumps(list(permissions), ensure_ascii=False),
    ]

    extra_env: dict[str, str] = {}

    if "fs:write" in permissions:
        try:
            folder = container.plugin_write_dir(module_path.stem)
            container.grant_write_scope(folder)
            extra_env[container.PLUGIN_OUT_ENV] = str(folder)
        except (OSError, container.ContainerError):
            pass

    try:
        code, output = container.run_text(
            command_args,
            cwd=root,
            timeout=timeout,
            extra_env=extra_env,
        )
    except container.ContainerError as error:
        return ToolResult(False, str(error))

    if code == -1:
        return ToolResult(False, output.strip() or "Контейнер не ответил.")

    return _parse_output(output.strip(), code)


def main(argv: list[str]) -> int:
    """Точка входа дочернего процесса."""

    if len(argv) < 4:
        print(
            json.dumps(
                {"ok": False, "text": "Неверные аргументы раннера."},
                ensure_ascii=False,
            )
        )

        return 2

    module_path = Path(argv[1]).resolve()
    root = Path(argv[2]).resolve()
    args = json.loads(argv[3])
    handler_name = argv[4] if len(argv) > 4 else "handler"
    permissions: tuple[str, ...] = ()

    if len(argv) > 5:
        try:
            parsed = json.loads(argv[5])

            if isinstance(parsed, list):
                permissions = tuple(
                    str(item) for item in parsed if isinstance(item, str)
                )
        except json.JSONDecodeError:
            permissions = ()

    try:
        result = execute_plugin(
            module_path,
            root,
            args,
            handler_name,
            permissions,
        )
    except Exception as error:  # noqa: BLE001 — ответим JSON-ошибкой
        result = ToolResult(
            False,
            f"Плагин упал при загрузке: {type(error).__name__}: {error}",
        )

    print(
        json.dumps(
            {"ok": result.ok, "text": result.text},
            ensure_ascii=False,
        )
    )

    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(BASE_DIR))
    raise SystemExit(main(sys.argv))
