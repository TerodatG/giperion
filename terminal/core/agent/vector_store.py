# Giperion/terminal/core/agent/vector_store.py                         v001
# Векторы фрагментов в SQLite вместо большого JSON.
# Последнее изменение: первый вариант — float32, миграция из JSON, лимит.

import json
import sqlite3
from array import array
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS vectors (
    hash TEXT NOT NULL,
    model TEXT NOT NULL,
    vector BLOB NOT NULL,
    created REAL NOT NULL DEFAULT (strftime('%s', 'now')),
    PRIMARY KEY (hash, model)
)
"""


def _connect(path: Path) -> sqlite3.Connection:
    """Открывает базу и создаёт таблицу при первом обращении."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target), timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(SCHEMA)

    return connection


def _legacy(path: Path) -> Path:
    """Старый JSON-кеш рядом с базой."""

    return Path(path).with_suffix(".json")


def _migrate(path: Path) -> None:
    """Переносит data/agent_vectors.json в SQLite один раз."""

    legacy = _legacy(path)

    if not legacy.exists():
        return

    try:
        document = json.loads(legacy.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    model = str(document.get("model") or "")
    vectors = document.get("vectors")

    if model and isinstance(vectors, dict):
        rows = {
            str(name): [float(value) for value in vector]
            for name, vector in vectors.items()
            if isinstance(vector, list) and vector
        }

        if rows:
            save(path, model, rows)

    try:
        legacy.unlink()
    except OSError:
        pass


def load(path: Path, model: str) -> dict[str, list[float]]:
    """Все векторы модели: хеш → список чисел."""

    _migrate(path)
    connection = _connect(path)

    try:
        rows = connection.execute(
            "SELECT hash, vector FROM vectors WHERE model = ?",
            (model,),
        ).fetchall()
    finally:
        connection.close()

    stored: dict[str, list[float]] = {}

    for name, blob in rows:
        values = array("f")
        values.frombytes(blob)
        stored[str(name)] = list(values)

    return stored


def save(
    path: Path,
    model: str,
    vectors: dict[str, list[float]],
    limit: int = 4000,
) -> None:
    """Пишет векторы и вытесняет самые старые сверх лимита."""

    if not vectors:
        return

    connection = _connect(path)

    try:
        connection.executemany(
            "INSERT OR REPLACE INTO vectors (hash, model, vector) "
            "VALUES (?, ?, ?)",
            [
                (
                    str(name),
                    model,
                    array("f", [float(value) for value in vector]).tobytes(),
                )
                for name, vector in vectors.items()
            ],
        )
        connection.execute(
            "DELETE FROM vectors WHERE model = ? AND hash NOT IN ("
            "SELECT hash FROM vectors WHERE model = ? "
            "ORDER BY created DESC LIMIT ?"
            ")",
            (model, model, max(1, int(limit))),
        )
        connection.commit()
    finally:
        connection.close()


def stats(path: Path, model: str) -> dict:
    """Сколько векторов и сколько места занимает база."""

    _migrate(path)
    target = Path(path)

    try:
        connection = _connect(target)

        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM vectors WHERE model = ?",
                (model,),
            ).fetchone()[0]
        finally:
            connection.close()
    except sqlite3.Error:
        return {"count": 0, "bytes": 0}

    try:
        size = target.stat().st_size
    except OSError:
        size = 0

    return {"count": int(count), "bytes": size}


def clear(path: Path) -> None:
    """Удаляет базу векторов и старый JSON-кеш."""

    for target in (Path(path), _legacy(path)):
        try:
            target.unlink()
        except OSError:
            pass
