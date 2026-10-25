# Giperion/tests/test_agent_summary.py                                v001
# Сводка изменений задачи: файлы, строки, дифф и кнопка отката.

import json
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from terminal.core.agent import tools
from terminal.core.agent.summary import (
    changes_of,
    describe_file,
    format_changes,
)


def _record(root, files, started=None) -> dict:
    return {
        "root": str(root),
        "files": list(files),
        "started_at": (started or (datetime.now() - timedelta(minutes=1)))
        .isoformat(timespec="seconds"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def test_change_summary_counts_lines(tmp_path) -> None:
    """Сводка считает добавленные и удалённые строки."""

    target = tmp_path / "a.txt"
    target.write_text("альфа\nбета\n", encoding="utf-8")

    started = datetime.now() - timedelta(seconds=1)
    tools.apply_patch(tmp_path, "a.txt", "бета", "гамма\nдельта")

    items = changes_of(tmp_path, _record(tmp_path, ["a.txt"], started))

    assert len(items) == 1
    assert items[0]["available"] is True
    assert items[0]["added"] == 2
    assert items[0]["removed"] == 1

    text = format_changes(items)

    assert "Изменено файлов: 1 (+2 −1)" in text
    assert "a.txt" in text
    assert "-бета" in text
    assert "+гамма" in text


def test_missing_backup_is_reported(tmp_path) -> None:
    """Без резервной копии файл помечается, сводка не падает."""

    item = describe_file(
        tmp_path,
        {"path": "нет.txt", "backup": None},
    )

    assert item["available"] is False
    assert item["note"] == "копия не найдена"

    text = format_changes([item], with_diff=False)

    assert "нет.txt" in text
    assert "копия не найдена" in text


def test_empty_summary(tmp_path) -> None:
    """Пустой список изменений формулируется явно."""

    assert format_changes([]) == "Изменённых файлов нет."


def test_job_collects_changes_after_run(tmp_path) -> None:
    """Job считает сводку после прогона и умеет отдать запись отката."""

    from terminal.ui.agent_job import AgentJob

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
    assert job.changes
    assert job.changes[0]["path"] == "a.txt"
    assert job.changes[0]["added"] == 1
    assert job.changes[0]["removed"] == 1

    record = job.rollback_record()

    assert record["files"] == ["a.txt"]
    assert record["started_at"]
    assert record["created_at"]


@pytest.fixture(scope="module")
def qapp():
    """Приложение Qt для окна агента."""

    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def test_dialog_shows_summary_and_undo(qapp, tmp_path) -> None:
    """Окно печатает сводку и показывает кнопку отката."""

    from terminal.ui.agent_dialog import AgentDialog

    dialog = AgentDialog(None)

    changes = [
        {
            "path": "a.txt",
            "available": True,
            "added": 1,
            "removed": 1,
            "diff": "-альфа\n+гамма",
            "note": "",
        }
    ]

    job = SimpleNamespace(
        steps=[],
        pending=None,
        done=True,
        cancelled=False,
        error="",
        answer="готово",
        duration_s=1.0,
        approvals=0,
        context_chars=100,
        allowed=set(),
        live_tokens=0,
        live_cost=0.0,
        partial="",
        tokens=0,
        cost=0.0,
        changed={"a.txt"},
        changes=changes,
        rollback_record=lambda: {
            "root": str(tmp_path),
            "files": ["a.txt"],
            "started_at": "2026-10-25T21:00:00",
            "created_at": "2026-10-25T21:01:00",
        },
    )

    dialog.job = job
    dialog._poll()

    text = dialog.trace.toPlainText()

    assert "ИЗМЕНЕНИЯ:" in text
    assert "a.txt" in text
    assert "+гамма" in text
    assert not dialog.undo_button.isHidden()

    dialog.job = None
    dialog.close()
