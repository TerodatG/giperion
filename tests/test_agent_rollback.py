# Giperion/tests/test_agent_rollback.py                               v001
# Откат прогона агента: файлы возвращаются из резервных копий.

import json
import time
from datetime import datetime, timedelta

from terminal.core.agent import git_tools, tools
from terminal.core.agent.rollback import (
    can_rollback,
    find_backup,
    parse_backup_name,
    plan_rollback,
    rollback_run,
)


def _record(root, files, started=None, finished=None) -> dict:
    return {
        "root": str(root),
        "files": list(files),
        "started_at": (started or (datetime.now() - timedelta(minutes=1)))
        .isoformat(timespec="seconds"),
        "created_at": (finished or datetime.now())
        .isoformat(timespec="seconds"),
    }


def test_backup_name_roundtrip() -> None:
    """Имя копии разбирается во время и путь."""

    parsed = parse_backup_name(
        "20261025-182731-163825-terminal__core__a.py"
    )

    assert parsed is not None
    moment, relative = parsed
    assert relative == "terminal/core/a.py"
    assert moment.year == 2026
    assert moment.month == 10

    assert parse_backup_name("мусор.txt") is None


def test_rollback_restores_edited_file(tmp_path) -> None:
    """Правка агента откатывается к состоянию до прогона."""

    target = tmp_path / "a.txt"
    target.write_text("альфа\n", encoding="utf-8")

    started = datetime.now() - timedelta(seconds=1)

    result = tools.apply_patch(tmp_path, "a.txt", "альфа", "гамма")
    assert result.ok

    record = _record(tmp_path, ["a.txt"], started=started)

    assert can_rollback(record)
    assert plan_rollback(tmp_path, record)[0]["backup"] is not None

    lines = rollback_run(tmp_path, record)

    assert lines == ["a.txt: восстановлен"]
    assert target.read_text(encoding="utf-8").startswith("альфа")


def test_rollback_restores_several_files(tmp_path) -> None:
    """Один прогон может вернуть несколько файлов."""

    (tmp_path / "a.txt").write_text("альфа\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("бета\n", encoding="utf-8")

    started = datetime.now() - timedelta(seconds=1)

    tools.apply_patch(tmp_path, "a.txt", "альфа", "гамма")
    tools.apply_patch(tmp_path, "b.txt", "бета", "дельта")

    record = _record(tmp_path, ["a.txt", "b.txt"], started=started)

    lines = rollback_run(tmp_path, record)

    assert len(lines) == 2
    assert (tmp_path / "a.txt").read_text(encoding="utf-8").startswith("альфа")
    assert (tmp_path / "b.txt").read_text(encoding="utf-8").startswith("бета")


def test_rollback_skips_backups_outside_window(tmp_path) -> None:
    """Копия, сделанная до прогона, не используется."""

    (tmp_path / "a.txt").write_text("альфа\n", encoding="utf-8")
    tools.apply_patch(tmp_path, "a.txt", "альфа", "гамма")

    later = datetime.now() + timedelta(minutes=5)
    record = _record(
        tmp_path,
        ["a.txt"],
        started=later,
        finished=later + timedelta(minutes=1),
    )

    assert find_backup(
        tmp_path,
        "a.txt",
        later,
        later + timedelta(minutes=1),
    ) is None

    lines = rollback_run(tmp_path, record)

    assert lines == ["a.txt: копия не найдена — пропущено"]
    assert (tmp_path / "a.txt").read_text(encoding="utf-8").startswith("гамма")


def test_record_without_files_has_nothing_to_roll_back() -> None:
    """Старые записи журнала без списка файлов не откатываются."""

    assert not can_rollback({"task": "старая"})
    assert plan_rollback("C:/tmp", {"files": []}) == []


def test_job_journal_contains_files_and_times(tmp_path, monkeypatch) -> None:
    """Журнал прогона хранит изменённые файлы и время старта."""

    from terminal.core.agent import runs
    from terminal.ui.agent_job import AgentJob

    journal = tmp_path / "agent_runs.jsonl"
    monkeypatch.setattr(runs, "RUNS_FILE", journal)

    (tmp_path / "a.txt").write_text("альфа\n", encoding="utf-8")

    class Brain:
        def __init__(self) -> None:
            self.answers = [
                json.dumps(
                    {
                        "action": "tool",
                        "tool": "apply_patch",
                        "args": {
                            "path": "a.txt",
                            "old": "альфа",
                            "new": "гамма",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {"action": "answer", "text": "готово"},
                    ensure_ascii=False,
                ),
            ]

        def decide(self, prompt: str) -> str:
            return self.answers.pop(0)

    job = AgentJob(
        "правь",
        Brain(),
        tmp_path,
        max_steps=4,
        policy="trust",
        persist=False,
    )

    deadline = time.time() + 3

    while time.time() < deadline and not job.done:
        time.sleep(0.02)

    assert job.done

    record = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])

    assert record["files"] == ["a.txt"]
    assert record["started_at"]
    assert record["root"] == str(tmp_path)


def test_git_commit_allows_several_paths(tmp_path) -> None:
    """Инструмент git_commit принимает массив путей."""

    from terminal.core.agent import registry
    from terminal.core.agent.protocol import ToolCall

    spec = registry.get_spec("git_commit")
    assert spec is not None
    assert spec.types.get("paths") == "array"

    schema = next(
        item
        for item in registry.tool_schemas()
        if item["function"]["name"] == "git_commit"
    )
    properties = schema["function"]["parameters"]["properties"]

    assert properties["paths"]["type"] == "array"
    assert properties["paths"]["items"] == {"type": "string"}

    invalid = registry.validate_call(
        ToolCall("git_commit", {"paths": "a.txt", "message": "x"})
    )
    assert invalid is not None

    valid = registry.validate_call(
        ToolCall(
            "git_commit",
            {"paths": ["a.txt", "b.txt"], "message": "x"},
        )
    )
    assert valid is None


def test_git_preview_lists_all_files(tmp_path) -> None:
    """Предпросмотр коммита показывает каждый файл."""

    (tmp_path / "a.txt").write_text("альфа\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("бета\n", encoding="utf-8")

    git_tools._run(tmp_path, ["init", "-q"])
    git_tools._run(tmp_path, ["config", "user.email", "a@b.c"])
    git_tools._run(tmp_path, ["config", "user.name", "Test"])
    git_tools._run(tmp_path, ["add", "a.txt", "b.txt"])
    git_tools._run(tmp_path, ["commit", "-q", "-m", "init"])

    (tmp_path / "a.txt").write_text("гамма\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("дельта\n", encoding="utf-8")

    preview = git_tools.git_preview_commit(
        tmp_path,
        "две правки",
        ["a.txt", "b.txt"],
    )

    assert "a.txt" in preview
    assert "b.txt" in preview
    assert "гамма" in preview
    assert "дельта" in preview
