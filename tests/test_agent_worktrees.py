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
    current_branch,
    is_repository,
    list_branches,
    list_worktrees,
    merge_worktree,
    remove_worktree,
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


def test_merge_brings_changes_to_main(repo) -> None:
    """Коммит из ветки агента попадает в основное дерево."""

    folder, branch = create_worktree(repo, "merge")

    (folder / "a.txt").write_text("бета\n", encoding="utf-8")
    _git(folder, "add", "a.txt")
    _git(folder, "commit", "-q", "-m", "change")

    message = merge_worktree(repo, branch)

    assert "бета" in (repo / "a.txt").read_text(encoding="utf-8")
    assert message


def test_merge_into_named_branch(repo) -> None:
    """Можно слить задачу в выбранную ветку, а не только в текущую."""

    _git(repo, "branch", "release")
    folder, branch = create_worktree(repo, "named")

    (folder / "a.txt").write_text("релиз\n", encoding="utf-8")
    _git(folder, "add", "a.txt")
    _git(folder, "commit", "-q", "-m", "change")

    merge_worktree(repo, branch, "release")

    shown = subprocess.run(
        [GIT, "show", "release:a.txt"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert "релиз" in shown.stdout
    assert current_branch(repo) not in ("release",)
    assert set(list_branches(repo)) >= {"release"}


def test_merge_rejects_missing_target(repo) -> None:
    """Несуществующая целевая ветка отклоняется."""

    _folder, branch = create_worktree(repo, "missing-target")

    with pytest.raises(WorktreeError):
        merge_worktree(repo, branch, "no-such-branch")


def test_merge_requires_clean_main(repo) -> None:
    """При незакоммиченных изменениях слияние запрещено."""

    _folder, branch = create_worktree(repo, "dirty")
    (repo / "a.txt").write_text("локально\n", encoding="utf-8")

    with pytest.raises(WorktreeError):
        merge_worktree(repo, branch)


def test_merge_conflict_explains_what_to_do(repo) -> None:
    """Конфликт отменяет слияние и объясняет, что делать дальше."""

    folder, branch = create_worktree(repo, "conflict")

    (folder / "a.txt").write_text("из ветки\n", encoding="utf-8")
    _git(folder, "commit", "-qam", "branch change")

    (repo / "a.txt").write_text("из основной\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "main change")

    with pytest.raises(WorktreeError) as error:
        merge_worktree(repo, branch)

    message = str(error.value)

    assert "Слияние не удалось" in message
    assert "разошлись" in message
    assert "a.txt" in message

    # Слияние отменено: основная ветка осталась со своими правками.
    assert (repo / "a.txt").read_text(encoding="utf-8") == "из основной\n"


def test_merge_conflict_can_use_ours(repo) -> None:
    """Стратегия ours оставляет версию основной ветки."""

    folder, branch = create_worktree(repo, "ours")

    (folder / "a.txt").write_text("из ветки\n", encoding="utf-8")
    _git(folder, "commit", "-qam", "branch change")

    (repo / "a.txt").write_text("из основной\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "main change")

    message = merge_worktree(repo, branch, strategy="ours")

    assert "merge" in message.lower() or message
    assert (repo / "a.txt").read_text(encoding="utf-8") == "из основной\n"


def test_remove_worktree_and_branch(repo) -> None:
    """Дерево и ветка удаляются, основное дерево остаётся."""

    folder, branch = create_worktree(repo, "remove")

    message = remove_worktree(repo, folder, branch)

    assert not folder.exists()
    assert message

    branches = subprocess.run(
        [GIT, "branch", "--list", branch],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert branches.stdout.strip() == ""


def test_remove_worktree_rejects_foreign_branch(repo) -> None:
    """Нельзя удалить дерево вместе с веткой вне agent/*."""

    folder, _branch = create_worktree(repo, "guard")

    with pytest.raises(WorktreeError):
        remove_worktree(repo, folder, "main")

    assert folder.exists()
