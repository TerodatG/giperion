# Giperion/tests/test_clean_caches.py                                  v001
# Очистка кешей: выбор файлов, сухой прогон и удаление.

import sys

from tools import clean_caches


def _prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(clean_caches, "DATA_DIR", tmp_path)
    (tmp_path / "agent_semantic.json").write_text("{}", encoding="utf-8")
    (tmp_path / "agent_vectors.db").write_text("db", encoding="utf-8")
    (tmp_path / "agent_index.json").write_text("{}", encoding="utf-8")


def test_targets_respects_flags(tmp_path, monkeypatch) -> None:
    """Флаги оставляют выбранные кеши на месте."""

    _prepare(tmp_path, monkeypatch)

    names = {
        path.name
        for _title, path in clean_caches.targets()
    }

    assert names == {
        "agent_semantic.json",
        "agent_vectors.db",
        "agent_index.json",
    }

    kept = {
        path.name
        for _title, path in clean_caches.targets(keep_vectors=True)
    }

    assert "agent_vectors.db" not in kept
    assert "agent_semantic.json" in kept


def test_dry_run_keeps_files(tmp_path, monkeypatch, capsys) -> None:
    """Без --yes ничего не удаляется."""

    _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["clean_caches"])

    assert clean_caches.main() == 0
    assert "Ничего не удалено" in capsys.readouterr().out
    assert (tmp_path / "agent_semantic.json").exists()


def test_yes_removes_files(tmp_path, monkeypatch, capsys) -> None:
    """С --yes файлы удаляются."""

    _prepare(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["clean_caches", "--yes"])

    assert clean_caches.main() == 0
    assert "Удалено файлов" in capsys.readouterr().out
    assert not (tmp_path / "agent_semantic.json").exists()
    assert not (tmp_path / "agent_vectors.db").exists()
