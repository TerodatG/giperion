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


def test_search_inside_one_file_does_not_touch_siblings(project) -> None:
    """Поиск по файлу не читает соседние файлы папки."""

    (project / "sub" / "c.py").write_text(
        "secret = 'сосед'\n",
        encoding="utf-8",
    )

    result = tools.search_text(project, "secret", "sub/b.py")

    assert result.ok
    assert "sub/b.py" in result.text
    assert "sub/c.py" not in result.text


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


def test_apply_patch_keeps_file_shape(project) -> None:
    """Лишние пустые строки по краям вставки не попадают в файл."""

    source = 'def greet():\n    return "Привет"\n'
    (project / "greet.py").write_text(source, encoding="utf-8")

    result = tools.apply_patch(
        project,
        "greet.py",
        'return "Привет"',
        '\nreturn "Здравствуйте"\n',
    )

    assert result.ok
    assert (project / "greet.py").read_text(encoding="utf-8") == (
        'def greet():\n    return "Здравствуйте"\n'
    )


def test_apply_patch_keeps_existing_blank_lines(project) -> None:
    """Пустые строки из оригинала сохраняются, лишние по краям — нет."""

    source = 'a = 1\n\nb = 2\n\n\nc = 3\n'
    (project / "code.py").write_text(source, encoding="utf-8")

    result = tools.apply_patch(
        project,
        "code.py",
        "\n\nb = 2",
        "\n\n\nb = 20",
    )

    assert result.ok
    assert (project / "code.py").read_text(encoding="utf-8") == (
        "a = 1\n\nb = 20\n\n\nc = 3\n"
    )


def test_apply_patch_matches_lf_fragment_in_crlf_file(project) -> None:
    """Фрагмент с LF находится в файле с CRLF и не портит переводы строк."""

    target = project / "crlf.py"
    target.write_bytes(
        b'def greet():\r\n\r\n    return "\xd0\x9f\xd1\x80\xd0\xb8\xd0\xb2'
        b'\xd0\xb5\xd1\x82"\r\n'
    )

    result = tools.apply_patch(
        project,
        "crlf.py",
        '\n\n    return "Привет"',
        '\n\n    return "Здравствуйте"',
    )

    assert result.ok
    assert target.read_bytes() == (
        b'def greet():\r\n\r\n    return "\xd0\x97\xd0\xb4\xd1\x80\xd0\xb0'
        b'\xd0\xb2\xd1\x81\xd1\x82\xd0\xb2\xd1\x83\xd0\xb9\xd1\x82\xd0\xb5"'
        b"\r\n"
    )


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

    from types import SimpleNamespace

    from terminal.core.agent import tools_exec

    monkeypatch.setattr(
        tools_exec.exec_sandbox,
        "run_python",
        lambda *args, **kwargs: SimpleNamespace(
            code=0,
            output="255 passed in 8s",
            timed_out=False,
            isolated=False,
        ),
    )

    result = tools.run_tests(project)

    assert result.ok
    assert "255 passed" in result.text
    assert "код 0" in result.text


def test_execution_dry_run_does_not_start(project, monkeypatch) -> None:
    """dry_run показывает команду и не запускает процесс."""

    def fail(*args, **kwargs):
        raise AssertionError("процесс не должен запускаться")

    monkeypatch.setattr(tools.subprocess, "run", fail)

    tests = tools.run_tests(project, dry_run=True)
    command = tools.run_command(
        project,
        "git status",
        dry_run=True,
    )

    assert tests.ok
    assert "pytest" in tests.text
    assert command.ok
    assert "status" in command.text


def test_bool_arg_parses_strings() -> None:
    """Строковые true/да понимаются как True."""

    from terminal.core.agent.protocol import ToolCall
    from terminal.core.agent.registry_specs import _bool_arg

    assert _bool_arg(ToolCall("run_tests", {"dry_run": True}), "dry_run")
    assert _bool_arg(ToolCall("run_tests", {"dry_run": "да"}), "dry_run")
    assert not _bool_arg(
        ToolCall("run_tests", {"dry_run": "нет"}),
        "dry_run",
    )


def test_repeated_write_is_idempotent(project) -> None:
    """Повторная запись того же текста не создаёт новую копию."""

    first = tools.write_file(project, "a.txt", "привет\nмир\n")

    assert first.ok
    assert "Записан" in first.text

    second = tools.write_file(project, "a.txt", "привет\nмир\n")

    assert second.ok
    assert "Без изменений" in second.text


def test_noop_patch_is_idempotent(project) -> None:
    """Замена фрагмента на тот же текст не перезаписывает файл."""

    result = tools.apply_patch(
        project,
        "a.txt",
        "привет",
        "привет",
    )

    assert result.ok
    assert "Без изменений" in result.text
