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


def _current_branch_or_error(base: Path) -> str:
    """Текущая ветка или ошибка."""

    current = _run(base, ["rev-parse", "--abbrev-ref", "HEAD"])

    if current.returncode != 0:
        raise WorktreeError("Не удалось определить текущую ветку.")

    return current.stdout.strip()


def _target_branch(base: Path, current: str, target: str) -> str:
    """Проверяет целевую ветку."""

    target_branch = str(target or current).strip()

    if target_branch.startswith("agent/"):
        raise WorktreeError("Целевой веткой не может быть ветка agent/*.")

    if target_branch != current:
        exists = _run(base, ["rev-parse", "--verify", target_branch])

        if exists.returncode != 0:
            raise WorktreeError(f"Ветки «{target_branch}» нет.")

    return target_branch


def _ensure_clean(base: Path) -> None:
    """Не даёт сливать поверх незакоммиченных правок."""

    dirty = _run(base, ["status", "--porcelain"])

    if dirty.returncode != 0:
        raise WorktreeError("Не удалось прочитать состояние git.")

    dirty_lines = [
        line
        for line in dirty.stdout.splitlines()
        if WORKTREE_DIR + "/" not in line
    ]

    if dirty_lines:
        raise WorktreeError(
            "В основном дереве есть незакоммиченные изменения — "
            "сначала закоммить или откати их."
        )


def _switch_to(base: Path, target: str, current: str) -> bool:
    """Переключает ветку; True — ветка менялась."""

    if target == current:
        return False

    switch = _run(base, ["switch", target])

    if switch.returncode != 0:
        detail = (switch.stderr or switch.stdout).strip()[:300]

        raise WorktreeError(f"Не удалось переключиться: {detail}")

    return True


def _merge_error(
    base: Path,
    name: str,
    current: str,
    switched: bool,
    result,
) -> None:
    """Откатывает неудачное слияние и поднимает ошибку."""

    conflicts = _run(
        base,
        ["diff", "--name-only", "--diff-filter=U"],
    ).stdout.splitlines()
    _run(base, ["merge", "--abort"])
    detail = (result.stderr or result.stdout).strip()[:500]

    if switched:
        _run(base, ["switch", current])

    hint = ""

    if "CONFLICT" in (result.stdout or "") or "CONFLICT" in detail:
        files = ", ".join(item.strip() for item in conflicts[:8])

        hint = (
            " Ветки разошлись по одним и тем же строкам: слияние "
            "отменено, файлы не тронуты. Открой задачу заново на "
            "свежей базе или перенеси правки вручную."
        )

        if files:
            hint += " Конфликты: " + files + "."

    raise WorktreeError(f"Слияние не удалось: {detail}{hint}")


def merge_worktree(
    root: Path,
    branch: str,
    target: str = "",
    strategy: str = "",
) -> str:
    """Сливает ветку агента в текущую или указанную ветку."""

    base = Path(root).resolve()

    if not is_repository(base):
        raise WorktreeError("Проект не является git-репозиторием.")

    name = str(branch or "").strip()

    if not name.startswith("agent/"):
        raise WorktreeError("Сливать можно только ветки agent/*.")

    chosen = str(strategy or "").strip().lower()

    if chosen not in ("", "ours", "theirs"):
        raise WorktreeError("Стратегия должна быть ours или theirs.")

    current = _current_branch_or_error(base)
    target_branch = _target_branch(base, current, target)
    _ensure_clean(base)
    switched = _switch_to(base, target_branch, current)
    command = ["merge", "--no-ff", "-m", f"merge {name}"]

    if chosen:
        command += ["-X", chosen]

    command.append(name)
    result = _run(base, command)

    if result.returncode != 0:
        _merge_error(base, name, current, switched, result)

    if switched:
        _run(base, ["switch", current])

    return (result.stdout or "Слито.").strip()[:1000]


def current_branch(root: Path) -> str:
    """Возвращает имя текущей ветки."""

    result = _run(Path(root).resolve(), ["rev-parse", "--abbrev-ref", "HEAD"])

    return result.stdout.strip() if result.returncode == 0 else ""


def list_branches(root: Path) -> list[str]:
    """Перечисляет локальные ветки, кроме веток агента."""

    result = _run(
        Path(root).resolve(),
        ["for-each-ref", "--format=%(refname:short)", "refs/heads"],
    )

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and not line.strip().startswith("agent/")
    ]


def remove_worktree(
    root: Path,
    path: Path,
    branch: str = "",
) -> str:
    """Удаляет рабочее дерево и, если указано, ветку."""

    base = Path(root).resolve()
    target = Path(path).resolve()
    allowed = (base / WORKTREE_DIR).resolve()

    if branch and not branch.startswith("agent/"):
        raise WorktreeError(
            "Удалять можно только ветки agent/*."
        )

    if target != allowed and allowed not in target.parents:
        raise WorktreeError("Удалять можно только деревья агента.")

    result = _run(
        base,
        ["worktree", "remove", "--force", str(target)],
    )

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[:300]

        raise WorktreeError(f"Не удалось убрать дерево: {detail}")

    if branch:
        _run(base, ["branch", "-D", branch])

    return f"Удалено дерево {target.name}."
