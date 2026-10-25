# Giperion/terminal/core/agent/plugin_runner.py                      v001
# Дочерний процесс для плагина: загрузка, вызов и JSON-ответ.
# Последнее изменение: изоляция плагинов от процесса Терминала.

import contextlib
import importlib.util
import io
import json
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
) -> ToolResult:
    """Выполняет плагин и возвращает результат."""

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
    ]

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = sandbox.plugin_env(BASE_DIR)

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
    lines = [line for line in output.splitlines() if line.strip()]

    if not lines:
        hint = _exit_hint(process.returncode)
        detail = (stderr or "").strip()[:300]

        if hint:
            return ToolResult(False, hint)

        return ToolResult(
            False,
            f"Плагин завершился без ответа (код {process.returncode}): "
            f"{detail or 'пусто'}",
        )

    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return ToolResult(
            False,
            "Плагин вернул не JSON: " + output[-400:],
        )

    if not isinstance(payload, dict):
        return ToolResult(False, "Плагин вернул не объект.")

    return ToolResult(
        bool(payload.get("ok")),
        str(payload.get("text") or "")[:MAX_OUTPUT],
    )


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

    try:
        result = execute_plugin(
            module_path,
            root,
            args,
            handler_name,
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
