# Giperion/tests/test_agent_watch.py                                  v001
# Наблюдатель за файлами: снимки, различия, debounce и настройки.

import json
import time

from terminal.core.agent import watch

from terminal.core.agent.watch import Changes, Watcher, diff, snapshot


def test_snapshot_ignores_service_folders(tmp_path) -> None:
    """data, .git и worktrees не попадают в снимок."""

    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "cache.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    (tmp_path / ".agent_worktrees").mkdir()
    (tmp_path / ".agent_worktrees" / "x.py").write_text("y", encoding="utf-8")
    (tmp_path / ".hidden").write_text("h", encoding="utf-8")

    files = snapshot(tmp_path)

    assert "a.py" in files
    assert not any(name.startswith("data/") for name in files)
    assert not any(name.startswith(".git/") for name in files)
    assert ".hidden" not in files
    assert not any(
        name.startswith(".agent_worktrees/") for name in files
    )


def test_diff_detects_all_kinds(tmp_path) -> None:
    """Различия находят новые, изменённые и удалённые файлы."""

    (tmp_path / "a.py").write_text("a", encoding="utf-8")
    (tmp_path / "b.py").write_text("b", encoding="utf-8")

    before = snapshot(tmp_path)

    (tmp_path / "a.py").write_text("a2", encoding="utf-8")
    (tmp_path / "b.py").unlink()
    (tmp_path / "c.py").write_text("c", encoding="utf-8")

    after = snapshot(tmp_path)
    changes = diff(before, after)

    assert changes.added == ["c.py"]
    assert changes.modified == ["a.py"]
    assert changes.deleted == ["b.py"]
    assert changes.total() == 3
    assert "новые" in changes.summary()
    assert "удалены" in changes.summary()


def test_changes_merge_and_bool() -> None:
    """Пустые изменения ложны, слияние убирает повторы."""

    empty = Changes()
    assert not empty
    assert empty.summary() == "изменений нет"

    empty.merge(Changes(added=["a"], modified=["b"]))
    empty.merge(Changes(added=["a"]))

    assert empty.added == ["a"]
    assert empty.modified == ["b"]
    assert empty


def test_watcher_reports_change(tmp_path) -> None:
    """После изменения и паузы watcher вызывает обработчик."""

    seen: list[Changes] = []

    watcher = Watcher(
        tmp_path,
        interval_s=0.1,
        debounce_s=0.1,
        cooldown_s=0.0,
    )
    watcher.start(on_change=seen.append)

    try:
        time.sleep(0.3)
        (tmp_path / "new.py").write_text("x", encoding="utf-8")

        deadline = time.time() + 4

        while time.time() < deadline and not seen:
            time.sleep(0.05)
    finally:
        watcher.stop()

    assert seen
    assert "new.py" in seen[0].added


def test_watcher_cooldown_suppresses_repeat(tmp_path) -> None:
    """Во время отдыха повторные изменения не будят задачу."""

    seen: list[Changes] = []

    watcher = Watcher(
        tmp_path,
        interval_s=0.1,
        debounce_s=0.0,
        cooldown_s=5.0,
    )
    watcher.start(on_change=seen.append)

    try:
        time.sleep(0.2)
        (tmp_path / "one.py").write_text("1", encoding="utf-8")

        deadline = time.time() + 3

        while time.time() < deadline and not seen:
            time.sleep(0.05)

        assert len(seen) == 1

        (tmp_path / "two.py").write_text("2", encoding="utf-8")
        time.sleep(0.8)

        assert len(seen) == 1
    finally:
        watcher.stop()


def test_watch_settings_roundtrip(tmp_path, monkeypatch) -> None:
    """Настройки наблюдателя сохраняются и подрезаются."""

    monkeypatch.setattr(
        watch,
        "SETTINGS_FILE",
        tmp_path / "agent_watch.json",
    )

    defaults = watch.load_settings()

    assert defaults.interval_s == 5.0
    assert defaults.auto_run is False

    watch.save_settings(
        watch.WatchSettings(
            enabled=True,
            interval_s=0.1,
            debounce_s=0.0,
            cooldown_s=9999.0,
            task="проверь",
            auto_run=True,
        )
    )

    loaded = watch.load_settings()

    assert loaded.interval_s == 1.0
    assert loaded.debounce_s == 0.0
    assert loaded.cooldown_s == 600.0
    assert loaded.task == "проверь"
    assert loaded.auto_run is True

    (tmp_path / "agent_watch.json").write_text(
        json.dumps({"interval_s": "долго"}),
        encoding="utf-8",
    )

    assert watch.load_settings().interval_s == 5.0
