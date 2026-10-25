# Giperion/terminal/core/agent/git_tools.py                          v001
# Git-инструменты агента: статус, дифф, журнал, коммит и откат.
# Последнее изменение: первый вариант — только чтение плюс явные действия.

import subprocess
from pathlib import Path

from terminal.core.agent.commands import _git_executable
from terminal.core.agent.protocol import ToolResult
from terminal.core.agent.tools import ToolError, safe_path
from shared.action_log import add_action

TIMEOUT = 60
MAX_OUTPUT = 4000


def _run(root: Path, args: list[str]) -> ToolResult:
    """Запускает git в папке проекта и обрезает вывод."""

    try:
        result = subprocess.run(
            [_git_executable(), *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, f"git не успел за {TIMEOUT} секунд.")
    except OSError as error:
        return ToolResult(False, f"Не удалось запустить git: {error}")

    output = (result.stdout + result.stderr).strip()
    text = output[-MAX_OUTPUT:] if output else "вывод пуст"

    return ToolResult(result.returncode == 0, text)


def _relative(root: Path, path: str) -> str:
    """Проверяет путь и возвращает его относительно проекта."""

    target = safe_path(root, path)

    return target.relative_to(Path(root).resolve()).as_posix()


def git_status(root: Path) -> ToolResult:
    """Показывает состояние рабочей копии."""

    return _run(root, ["status", "--short", "--branch"])


def git_diff(root: Path, path: str = "") -> ToolResult:
    """Показывает незакоммиченные изменения."""

    args = ["diff", "--"]

    if str(path or "").strip():
        try:
            args.append(_relative(root, path))
        except ToolError as error:
            return ToolResult(False, str(error))

    return _run(root, args)


def git_log(root: Path, limit: int = 5) -> ToolResult:
    """Показывает последние коммиты."""

    try:
        count = max(1, min(int(limit or 5), 20))
    except (TypeError, ValueError):
        count = 5

    return _run(root, ["log", f"-{count}", "--oneline"])


def git_commit(
    root: Path,
    message: str,
    path: str,
) -> ToolResult:
    """Коммитит один файл с сообщением."""

    text = str(message or "").strip()

    if not text:
        return ToolResult(False, "Нужно сообщение коммита.")

    if len(text) > 200:
        return ToolResult(False, "Сообщение коммита слишком длинное.")

    try:
        relative = _relative(root, path)
    except ToolError as error:
        return ToolResult(False, str(error))

    added = _run(root, ["add", "--", relative])

    if not added.ok:
        return added

    result = _run(
        root,
        ["commit", "-m", text, "--", relative],
    )

    if result.ok:
        add_action(f"Агент: коммит {relative}")

    return result


def git_restore(root: Path, path: str) -> ToolResult:
    """Откатывает незакоммиченные изменения одного файла."""

    try:
        relative = _relative(root, path)
    except ToolError as error:
        return ToolResult(False, str(error))

    result = _run(root, ["restore", "--", relative])

    if result.ok:
        add_action(f"Агент: откат {relative}")

    return result


def git_preview_commit(
    root: Path,
    message: str,
    path: str,
) -> str:
    """Описание коммита для окна подтверждения."""

    diff = git_diff(root, path)
    body = diff.text if diff.ok else diff.text

    return (
        f"git add -- {path}\n"
        f"git commit -m {message!r} -- {path}\n\n"
        f"{body}"
    )


def git_preview_restore(root: Path, path: str) -> str:
    """Показывает, какие изменения будут потеряны при откате."""

    diff = git_diff(root, path)

    return "git restore -- " + path + "\n\n" + diff.text
