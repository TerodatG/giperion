# Giperion/tests/test_migrate_data.py                                   v001
# Миграции data/: версия, каталоги и резервная копия.

from tools import backup_data, migrate_data


def test_migrate_creates_dirs_and_version(tmp_path, monkeypatch) -> None:
    """Миграция создаёт каталоги, версию и pre-migrate архив."""

    (tmp_path / "agent_tasks").mkdir()
    (tmp_path / "agent_tasks" / "a.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(backup_data, "DATA_DIR", tmp_path)

    steps = migrate_data.migrate(tmp_path)

    assert migrate_data.read_version(
        tmp_path / "schema_version.json"
    ) == migrate_data.CURRENT_VERSION
    assert (tmp_path / "agent_memory").is_dir()
    assert (tmp_path / "agent_nightly").is_dir()
    assert any("резервная копия" in step for step in steps)
    assert list((tmp_path / "backups").glob("pre-migrate-*.zip"))


def test_dry_run_changes_nothing(tmp_path, monkeypatch) -> None:
    """dry-run только перечисляет шаги."""

    monkeypatch.setattr(backup_data, "DATA_DIR", tmp_path)

    steps = migrate_data.migrate(tmp_path, dry_run=True)

    assert any("каталог: agent_memory" in step for step in steps)
    assert not (tmp_path / "schema_version.json").exists()
    assert not (tmp_path / "agent_memory").exists()


def test_invalid_version_is_zero(tmp_path) -> None:
    """Битый файл версии считается нулевой версией."""

    path = tmp_path / "schema_version.json"
    path.write_text("{bad", encoding="utf-8")

    assert migrate_data.read_version(path) == 0


def test_repeat_migration_is_noop(tmp_path, monkeypatch) -> None:
    """Повторная миграция не делает работу."""

    monkeypatch.setattr(backup_data, "DATA_DIR", tmp_path)
    migrate_data.migrate(tmp_path)

    assert migrate_data.migrate(tmp_path) == ["уже актуально: v1"]
