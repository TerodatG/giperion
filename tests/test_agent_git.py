# Giperion/tests/test_agent_git.py                                   v001
# Git-инструменты агента на временном репозитории.

import shutil
import subprocess
from pathlib import Path

import pytest

from terminal.core.agent import git_tools
from terminal.core.agent.commands import _git_executable

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
    """Пустой git-репозиторий с одним файлом."""

    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "agent@test.local")
    _git(tmp_path, "config", "user.name", "Agent Test")
    (tmp_path / "a.txt").write_text("альфа\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")

    return tmp_path


def test_status_shows_clean_repo(repo) -> None:
    """Статус читается и показывает ветку."""

    result = git_tools.git_status(repo)

    assert result.ok
    assert "##" in result.text


def test_diff_shows_changes(repo) -> None:
    """Дифф показывает незакоммиченную правку."""

    (repo / "a.txt").write_text("бета\n", encoding="utf-8")

    result = git_tools.git_diff(repo, "a.txt")

    assert result.ok
    assert "бета" in result.text
    assert "альфа" in result.text


def test_commit_saves_one_file(repo) -> None:
    """Коммит сохраняет файл и появляется в журнале."""

    (repo / "a.txt").write_text("бета\n", encoding="utf-8")

    result = git_tools.git_commit(repo, "правка агента", "a.txt")

    assert result.ok

    status = git_tools.git_status(repo)
    assert "a.txt" not in status.text

    log = git_tools.git_log(repo, 3)
    assert "правка агента" in log.text


def test_restore_returns_original(repo) -> None:
    """Откат возвращает исходный текст файла."""

    (repo / "a.txt").write_text("испорчено\n", encoding="utf-8")

    result = git_tools.git_restore(repo, "a.txt")

    assert result.ok
    assert (repo / "a.txt").read_text(encoding="utf-8") == "альфа\n"


def test_git_diff_denies_path_outside(repo) -> None:
    """Путь за пределами проекта не принимается."""

    result = git_tools.git_diff(repo, "../secret.txt")

    assert not result.ok


def test_commit_preview_contains_diff(repo) -> None:
    """Перед коммитом пользователь видит дифф."""

    (repo / "a.txt").write_text("гамма\n", encoding="utf-8")

    preview = git_tools.git_preview_commit(
        repo,
        "ещё правка",
        "a.txt",
    )

    assert "git commit" in preview
    assert "гамма" in preview


def test_commit_requires_message(repo) -> None:
    """Пустое сообщение коммита отклоняется."""

    (repo / "a.txt").write_text("бета\n", encoding="utf-8")

    result = git_tools.git_commit(repo, "   ", "a.txt")

    assert not result.ok
