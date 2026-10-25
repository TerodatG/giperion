# Giperion/tests/test_agent_worktrees.py                             v001
# Отдельные рабочие деревья git для параллельных задач агента.

import shutil
import subprocess
from pathlib import Path

import pytest

from terminal.core.agent.commands import _git_executable
from terminal.core.agent.worktrees import (
    WorktreeError,
    create_worktree,
    is_repository,
    list_worktrees,
    slugify,
)

GIT = _git_executable()

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None
    and not Path(r"C:\Program Files\Git\cmd\git.exe").exists(),
    reason="git не установлен",
)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        [GIT, *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.fixture()
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "agent@test.local")
    _git(tmp_path, "config", "user.name", "Agent Test")
    (tmp_path / "a.txt").write_text("альфа\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")

    return tmp_path


def test_slug_is_safe() -> None:
    """Имя ветки не содержит пробелов и странных символов."""

    assert slugify("Почини кнопку!") == "почини-кнопку"
    assert slugify("   ") == "task"


def test_create_worktree(repo) -> None:
    """Дерево и ветка создаются внутри проекта."""

    folder, branch = create_worktree(repo, "кнопка агента")

    assert folder.is_dir()
    assert (folder / "a.txt").is_file()
    assert branch.startswith("agent/")
    assert ".agent_worktrees" in str(folder)

    listing = list_worktrees(repo)
    assert branch.split("/")[-1] in listing


def test_duplicate_worktree_is_rejected(repo) -> None:
    """Повторное имя дерева не создаёт второй worktree."""

    create_worktree(repo, "dup")

    with pytest.raises(WorktreeError):
        create_worktree(repo, "dup")


def test_non_repository_is_rejected(tmp_path) -> None:
    """В обычной папке worktree не создаётся."""

    assert not is_repository(tmp_path)

    with pytest.raises(WorktreeError):
        create_worktree(tmp_path, "task")
