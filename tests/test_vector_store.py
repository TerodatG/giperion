# Giperion/tests/test_vector_store.py                                  v001
# SQLite-хранилище векторов: запись, чтение, миграция и лимит.

import json
import sqlite3

from terminal.core.agent import vector_store


def test_save_and_load_by_model(tmp_path) -> None:
    """Векторы хранятся отдельно для каждой модели."""

    path = tmp_path / "vectors.db"

    vector_store.save(
        path,
        "model-a",
        {"a": [1.0, 0.5], "b": [0.0, 1.0]},
    )

    stored = vector_store.load(path, "model-a")

    assert stored["a"] == [1.0, 0.5]
    assert stored["b"] == [0.0, 1.0]
    assert vector_store.load(path, "model-b") == {}


def test_limit_evicts_old_rows(tmp_path) -> None:
    """Сверх лимита остаются не больше N векторов."""

    path = tmp_path / "vectors.db"

    vector_store.save(
        path,
        "model",
        {f"h{index}": [float(index)] for index in range(10)},
        limit=3,
    )

    stored = vector_store.load(path, "model")

    assert len(stored) <= 3
    assert stored


def test_migrates_legacy_json(tmp_path) -> None:
    """Старый JSON-кеш переносится в SQLite и удаляется."""

    path = tmp_path / "vectors.db"
    legacy = tmp_path / "vectors.json"
    legacy.write_text(
        json.dumps(
            {
                "model": "old",
                "vectors": {"x": [1.0, 2.0]},
            }
        ),
        encoding="utf-8",
    )

    stored = vector_store.load(path, "old")

    assert stored == {"x": [1.0, 2.0]}
    assert not legacy.exists()
    assert path.exists()


def test_stats_and_clear(tmp_path) -> None:
    """Статистика считает записи, clear удаляет базу."""

    path = tmp_path / "vectors.db"

    vector_store.save(path, "model", {"a": [1.0]})

    stats = vector_store.stats(path, "model")

    assert stats["count"] == 1
    assert stats["bytes"] > 0

    vector_store.clear(path)

    assert not path.exists()
    assert vector_store.load(path, "model") == {}


def test_broken_vector_is_skipped_on_migration(tmp_path) -> None:
    """Битые записи старого кеша не ломают миграцию."""

    path = tmp_path / "vectors.db"
    legacy = tmp_path / "vectors.json"
    legacy.write_text(
        json.dumps(
            {
                "model": "old",
                "vectors": {
                    "good": [1.0],
                    "bad": "не список",
                    "empty": [],
                },
            }
        ),
        encoding="utf-8",
    )

    stored = vector_store.load(path, "old")

    assert stored == {"good": [1.0]}


def test_schema_is_sqlite(tmp_path) -> None:
    """Файл — настоящая база, а не JSON."""

    path = tmp_path / "vectors.db"

    vector_store.save(path, "model", {"a": [1.0]})

    with sqlite3.connect(path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM vectors"
        ).fetchone()[0]

    assert count == 1
