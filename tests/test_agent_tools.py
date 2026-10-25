# Giperion/tests/test_agent_tools.py                                 v001
# Read-only инструменты агента: пути, чтение, поиск, запреты.

import pytest

from terminal.core.agent import tools


@pytest.fixture()
def project(tmp_path):
    """Маленький проект с текстовыми файлами и секретами."""

    (tmp_path / "a.txt").write_text(
        "привет\nмир\n",
        encoding="utf-8",
    )
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text(
        "answer = 42\nsecret = 'нет'\n",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("TOKEN=секрет", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "conversations.json").write_text(
        "[]",
        encoding="utf-8",
    )
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02")
    (tmp_path / "outside.txt").write_text("внутри", encoding="utf-8")

    return tmp_path


def test_list_dir_shows_project(project) -> None:
    """Список папки показывает файлы и каталоги проекта."""

    result = tools.list_dir(project, ".")

    assert result.ok
    assert "a.txt" in result.text
    assert "sub/" in result.text
    assert ".env" not in result.text


def test_read_file_returns_text(project) -> None:
    """Чтение файла отдаёт содержимое и число строк."""

    result = tools.read_file(project, "a.txt")

    assert result.ok
    assert "привет" in result.text
    assert "строк" in result.text


def test_path_outside_project_is_denied(project) -> None:
    """Выйти за корень проекта нельзя."""

    result = tools.read_file(project, "../outside.txt")

    assert not result.ok
    assert "вне рабочей папки" in result.text


def test_secrets_are_denied(project) -> None:
    """Секреты и личные данные закрыты даже для чтения."""

    env = tools.read_file(project, ".env")
    conversations = tools.read_file(
        project,
        "data/conversations.json",
    )

    assert not env.ok
    assert not conversations.ok


def test_binary_is_denied(project) -> None:
    """Двоичные файлы агент не читает."""

    result = tools.read_file(project, "binary.bin")

    assert not result.ok
    assert "двоичный" in result.text


def test_search_finds_lines(project) -> None:
    """Поиск возвращает путь, номер строки и текст."""

    result = tools.search_text(project, "answer")

    assert result.ok
    assert "sub/b.py:1" in result.text


def test_search_needs_two_characters(project) -> None:
    """Слишком короткий запрос отклоняется."""

    result = tools.search_text(project, "a")

    assert not result.ok


def test_archive_and_logs_are_denied(project) -> None:
    """Архивы и журналы закрыты: там личная история."""

    (project / "archive").mkdir()
    (project / "archive" / "chat.json").write_text(
        "[]",
        encoding="utf-8",
    )

    result = tools.read_file(project, "archive/chat.json")

    assert not result.ok
    assert "закрыты" in result.text


def test_apply_patch_changes_unique_fragment(project) -> None:
    """Патч меняет один фрагмент и оставляет резервную копию."""

    result = tools.apply_patch(project, "a.txt", "мир", "планета")

    assert result.ok
    assert "планета" in (
        project / "a.txt"
    ).read_text(encoding="utf-8")
    assert "agent_backups" in result.text


def test_apply_patch_rejects_ambiguous_fragment(project) -> None:
    """Если фрагмент встречается дважды, патч не применяется."""

    (project / "dup.txt").write_text("x\nx\n", encoding="utf-8")

    result = tools.apply_patch(project, "dup.txt", "x", "y")

    assert not result.ok
    assert "2" in result.text
    assert (project / "dup.txt").read_text(encoding="utf-8") == "x\nx\n"


def test_write_file_creates_new_file(project) -> None:
    """Новый файл создаётся, а не только перезаписывается."""

    result = tools.write_file(project, "new.txt", "привет")

    assert result.ok
    assert (project / "new.txt").read_text(encoding="utf-8") == "привет"
    assert "новый файл" in result.text


def test_write_file_denies_secrets(project) -> None:
    """Секреты нельзя перезаписать через агента."""

    result = tools.write_file(project, ".env", "TOKEN=x")

    assert not result.ok


def test_run_tests_reports_output(project, monkeypatch) -> None:
    """Запуск тестов возвращает код и хвост вывода."""

    class Result:
        returncode = 0
        stdout = "255 passed in 8s"
        stderr = ""

    monkeypatch.setattr(
        tools.subprocess,
        "run",
        lambda *args, **kwargs: Result(),
    )

    result = tools.run_tests(project)

    assert result.ok
    assert "255 passed" in result.text
    assert "код 0" in result.text
