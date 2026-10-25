# Giperion/terminal/core/agent/worktrees.py                         v001
# Отдельные рабочие деревья git для параллельных задач агента.
# Последнее изменение: первый вариант — создание и список.

import re
import subprocess
from pathlib import Path

from terminal.core.agent.commands import _git_executable

TIMEOUT = 60
WORKTREE_DIR = ".agent_worktrees"


class WorktreeError(RuntimeError):
    """Не удалось создать или прочитать рабочее дерево."""


def slugify(name: str) -> str:
    """Превращает имя задачи в безопасный slug ветки."""

    text = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ]+", "-", name.lower())
    text = text.strip("-")[:30]

    return text or "task"


def _run(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [_git_executable(), *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise WorktreeError(f"git не запустился: {error}") from error


def is_repository(root: Path) -> bool:
    """Проверяет, что папка — корень git-репозитория."""

    result = _run(Path(root), ["rev-parse", "--show-toplevel"])

    if result.returncode != 0:
        return False

    top = result.stdout.strip()

    return bool(top) and Path(top).resolve() == Path(root).resolve()


def create_worktree(root: Path, name: str) -> tuple[Path, str]:
    """Создаёт отдельное дерево и ветку для задачи."""

    base = Path(root).resolve()

    if not is_repository(base):
        raise WorktreeError("Проект не является корнем git-репозитория.")

    slug = slugify(name)
    folder = base / WORKTREE_DIR / slug
    branch = f"agent/{slug}"

    if folder.exists():
        raise WorktreeError(f"Дерево уже существует: {folder}")

    folder.parent.mkdir(parents=True, exist_ok=True)

    result = _run(
        base,
        ["worktree", "add", "-b", branch, str(folder)],
    )

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[:300]

        raise WorktreeError(f"git worktree add не удался: {detail}")

    return folder, branch


def list_worktrees(root: Path) -> str:
    """Показывает рабочие деревья репозитория."""

    base = Path(root).resolve()
    result = _run(base, ["worktree", "list"])

    if result.returncode != 0:
        raise WorktreeError(
            (result.stderr or result.stdout).strip()[:300]
        )

    return result.stdout.strip()
