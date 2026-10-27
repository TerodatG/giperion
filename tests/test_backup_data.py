# Giperion/tests/test_backup_data.py                                    v001
# Резервная копия data/: секреты, manifest и безопасное восстановление.

import zipfile

import pytest

from tools import backup_data


def _data(tmp_path, monkeypatch):
    root = tmp_path / "data"
    (root / "agent_tasks").mkdir(parents=True)
    (root / "agent_tasks" / "a.json").write_text("{}", encoding="utf-8")
    (root / "agent_memory").mkdir()
    (root / "agent_memory" / "p.md").write_text("заметка", encoding="utf-8")
    (root / "agent_api_token").write_text("secret", encoding="utf-8")
    monkeypatch.setattr(backup_data, "DATA_DIR", root)

    return root


def test_create_skips_secrets_by_default(tmp_path, monkeypatch) -> None:
    """В архив не попадают токены и ключи без флага."""

    _data(tmp_path, monkeypatch)
    archive = backup_data.create()

    with zipfile.ZipFile(archive) as source:
        names = source.namelist()

    assert "agent_tasks/a.json" in names
    assert "agent_memory/p.md" in names
    assert "agent_api_token" not in names
    assert "manifest.json" in names


def test_restore_roundtrip(tmp_path, monkeypatch) -> None:
    """Файлы восстанавливаются, существующие не перезаписываются."""

    _data(tmp_path, monkeypatch)
    archive = backup_data.create(with_secrets=True)
    target = tmp_path / "restored"

    assert backup_data.restore(archive, target) == 3
    assert (target / "agent_memory" / "p.md").read_text(
        encoding="utf-8"
    ) == "заметка"

    (target / "agent_memory" / "p.md").write_text(
        "новая",
        encoding="utf-8",
    )

    assert backup_data.restore(archive, target) == 0
    assert backup_data.restore(archive, target, force=True) == 3
    assert (target / "agent_memory" / "p.md").read_text(
        encoding="utf-8"
    ) == "заметка"


def test_restore_rejects_traversal(tmp_path) -> None:
    """Путь с .. не распаковывается."""

    archive = tmp_path / "bad.zip"

    with zipfile.ZipFile(archive, "w") as source:
        source.writestr("../evil.txt", "x")

    with pytest.raises(ValueError, match="Небезопасный"):
        backup_data.restore(archive, tmp_path / "out")
