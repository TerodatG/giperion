# Giperion/terminal/core/agent/commands.py                          v001
# Белый список команд агента: без shell и разрушительных подкоманд.
# Последнее изменение: первый вариант — git-чтение, pytest, compileall.

import shlex
import sys

GIT_READ_SUBCOMMANDS = {
    "status",
    "diff",
    "log",
    "show",
    "rev-parse",
    "ls-files",
}

PYTHON_MODULES = {"pytest", "compileall"}

DENY_TOKENS = (
    ";",
    "&&",
    "||",
    "|",
    ">",
    "<",
    "`",
    "$(",
    "\n",
    "\r",
)

PYTHON_NAMES = {"python", "python3", "python3.13", "py", "pytest"}


class CommandError(ValueError):
    """Команда не прошла белый список."""


def _git_executable() -> str:
    """Ищет git, если его нет в PATH текущего процесса."""

    import shutil

    found = shutil.which("git")

    if found:
        return found

    for candidate in (
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
    ):
        from pathlib import Path

        if Path(candidate).exists():
            return candidate

    return "git"


def validate_command(command: str) -> list[str]:
    """Разбирает команду и проверяет её по белому списку."""

    text = str(command or "").strip()

    if not text:
        raise CommandError("Пустая команда.")

    if len(text) > 500:
        raise CommandError("Команда слишком длинная.")

    for token in DENY_TOKENS:
        if token in text:
            raise CommandError(
                f"Символ «{token}» запрещён: shell-операторы не поддерживаются."
            )

    try:
        parts = shlex.split(text, posix=False)
    except ValueError as error:
        raise CommandError(f"Не разобрать команду: {error}") from error

    parts = [part.strip("\"'") for part in parts if part.strip()]

    if not parts:
        raise CommandError("Пустая команда.")

    executable = parts[0].lower()

    if executable.endswith(".exe"):
        executable = executable[:-4]

    if executable == "git":
        if len(parts) < 2:
            raise CommandError("У git нужна подкоманда.")

        subcommand = parts[1].lower()

        if subcommand not in GIT_READ_SUBCOMMANDS:
            raise CommandError(
                "Разрешены только git "
                + ", ".join(sorted(GIT_READ_SUBCOMMANDS))
                + ". Для коммита и отката есть отдельные инструменты."
            )

        parts[0] = _git_executable()

        return parts

    if executable in PYTHON_NAMES:
        if executable == "pytest":
            return [sys.executable, "-m", "pytest", *parts[1:]]

        if len(parts) < 3 or parts[1] != "-m":
            raise CommandError(
                "Python разрешён только как «python -m pytest» "
                "или «python -m compileall»."
            )

        module = parts[2].lower()

        if module not in PYTHON_MODULES:
            raise CommandError(
                "Разрешены только модули: "
                + ", ".join(sorted(PYTHON_MODULES))
                + "."
            )

        return [sys.executable, "-m", module, *parts[3:]]

    raise CommandError(
        f"Команда «{parts[0]}» не входит в белый список."
    )
