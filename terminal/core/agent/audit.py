# Giperion/terminal/core/agent/audit.py                                v001
# Аудит действий агента: JSONL с хеш-цепочкой.
# Последнее изменение: первый вариант — record, verify, tail.

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path

from config import DATA_DIR
from terminal.core.agent.redact import redact

AUDIT_FILE = DATA_DIR / "agent_audit.jsonl"
GENESIS = "0" * 64
_LOCK = threading.Lock()


def _last_hash(path: Path) -> str:
    """Хеш последней записи или genesis."""

    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return GENESIS

    for line in reversed(lines):
        text = line.strip()

        if not text:
            continue

        try:
            return str(json.loads(text).get("hash") or GENESIS)
        except json.JSONDecodeError:
            return GENESIS

    return GENESIS


def _digest(entry: dict) -> str:
    """Хеш записи вместе с предыдущим хешем."""

    body = {
        key: value
        for key, value in entry.items()
        if key != "hash"
    }
    text = json.dumps(body, ensure_ascii=False, sort_keys=True)

    return hashlib.sha256(
        (str(body.get("prev") or "") + text).encode("utf-8")
    ).hexdigest()


def record(
    event: str,
    payload: dict | None = None,
    path: Path | None = None,
) -> dict:
    """Добавляет событие в аудит и возвращает запись."""

    target = Path(path or AUDIT_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)

    with _LOCK:
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": str(event),
            "payload": payload or {},
            "prev": _last_hash(target),
        }
        entry["hash"] = _digest(entry)

        with target.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(entry, ensure_ascii=False) + "\n"
            )

    return entry


def verify(path: Path | None = None) -> tuple[bool, str]:
    """Проверяет цепочку: каждая запись ссылается на предыдущую."""

    target = Path(path or AUDIT_FILE)

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return True, "журнал пуст"

    prev = GENESIS
    count = 0

    for number, line in enumerate(lines, start=1):
        text = line.strip()

        if not text:
            continue

        try:
            entry = json.loads(text)
        except json.JSONDecodeError:
            return False, f"строка {number}: не JSON"

        if str(entry.get("prev")) != prev:
            return False, f"строка {number}: разорвана цепочка"

        if str(entry.get("hash")) != _digest(entry):
            return False, f"строка {number}: подмена записи"

        prev = str(entry.get("hash"))
        count += 1

    return True, f"записей: {count}"


def tail(limit: int = 5, path: Path | None = None) -> list[dict]:
    """Последние записи аудита."""

    target = Path(path or AUDIT_FILE)

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    result = []

    for line in lines[-max(1, int(limit)):]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(value, dict):
            result.append(value)

    return result


def target_of(payload: dict) -> str:
    """Короткое и безопасное описание цели действия."""

    for key in ("path", "url", "command", "query"):
        value = payload.get(key)

        if value:
            return redact(str(value)).text[:200]

    return ""
