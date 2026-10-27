# Giperion/terminal/core/agent/audit.py                                v001
# Аудит действий агента: JSONL с хеш-цепочкой.
# Последнее изменение: первый вариант — record, verify, tail.

import hashlib
import hmac
import json
import os
import secrets
import threading
from datetime import datetime, timedelta
from pathlib import Path

from config import DATA_DIR
from terminal.core.agent.redact import redact

AUDIT_FILE = DATA_DIR / "agent_audit.jsonl"
AUDIT_KEY_FILE = DATA_DIR / "audit_export.key"
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


def _clean(value):
    """Рекурсивно вырезает секреты из полезной нагрузки."""

    if isinstance(value, str):
        return redact(value).text

    if isinstance(value, dict):
        return {
            str(key): _clean(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_clean(item) for item in value]

    return value


def record(
    event: str,
    payload: dict | None = None,
    path: Path | None = None,
) -> dict:
    """Добавляет событие в аудит и возвращает запись."""

    target = Path(path or AUDIT_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = _clean(payload or {})

    with _LOCK:
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": str(event),
            "payload": clean,
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


def prune(
    days: int = 90,
    path: Path | None = None,
    archive_dir: Path | None = None,
) -> int:
    """Переносит старые записи в архив и пересобирает активную цепочку."""

    target = Path(path or AUDIT_FILE)

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0

    cutoff = (
        datetime.now() - timedelta(days=max(1, int(days)))
    ).isoformat(timespec="seconds")
    old: list[str] = []
    keep: list[str] = []

    for line in lines:
        text = line.strip()

        if not text:
            continue

        try:
            entry = json.loads(text)
        except json.JSONDecodeError:
            continue

        if str(entry.get("ts") or "") < cutoff:
            old.append(text)
        else:
            keep.append(text)

    if not old:
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    archive = Path(
        archive_dir or target.parent
    ) / (
        f"{target.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        ".jsonl"
    )
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("\n".join(old) + "\n", encoding="utf-8")
    anchor = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": "audit.rotate",
        "payload": {
            "archive": archive.name,
            "archived": len(old),
        },
        "prev": GENESIS,
    }
    anchor["hash"] = _digest(anchor)
    rebuilt = [anchor]

    for line in keep:
        entry = json.loads(line)
        entry["prev"] = rebuilt[-1]["hash"]
        entry["hash"] = _digest(entry)
        rebuilt.append(entry)

    content = "\n".join(
        json.dumps(entry, ensure_ascii=False)
        for entry in rebuilt
    )
    temp = target.with_name(target.name + ".tmp")
    temp.write_text(content + "\n", encoding="utf-8")
    temp.replace(target)

    return len(old)


def _key(key_file: Path | None = None, create: bool = True) -> bytes:
    """Ключ экспорта аудита."""

    path = Path(key_file or AUDIT_KEY_FILE)

    if not path.exists() and create:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32), encoding="utf-8")

        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ValueError(f"Ключ аудита не найден: {path}") from error

    if len(text) < 32:
        raise ValueError("Ключ аудита слишком короткий.")

    return text.encode("utf-8")


def _sign(payload: bytes, key: bytes) -> str:
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def export(
    target: Path,
    path: Path | None = None,
    key_file: Path | None = None,
    since: str = "",
    until: str = "",
) -> tuple[Path, Path]:
    """Экспортирует записи и кладёт рядом подпись HMAC."""

    source = Path(path or AUDIT_FILE)
    output = Path(target)
    entries = []

    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []

    for line in lines:
        text = line.strip()

        if not text:
            continue

        try:
            entry = json.loads(text)
        except json.JSONDecodeError:
            continue

        stamp = str(entry.get("ts") or "")

        if since and stamp < since:
            continue

        if until and stamp > until:
            continue

        entries.append(entry)

    payload = "\n".join(
        json.dumps(entry, ensure_ascii=False, sort_keys=True)
        for entry in entries
    )
    data = (payload + ("\n" if payload else "")).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    signature = {
        "algorithm": "hmac-sha256",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "records": len(entries),
        "signature": _sign(data, _key(key_file)),
    }
    sig_path = output.with_name(output.name + ".sig")
    sig_path.write_text(
        json.dumps(signature, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return output, sig_path


def verify_export(
    target: Path,
    signature: Path | None = None,
    key_file: Path | None = None,
) -> tuple[bool, str]:
    """Проверяет подпись экспортированного журнала."""

    path = Path(target)
    sig_path = signature or path.with_name(path.name + ".sig")

    try:
        signature_data = json.loads(sig_path.read_text(encoding="utf-8"))
        key = _key(key_file, create=False)
        data = path.read_bytes()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return False, str(error)

    expected = _sign(data, key)
    actual = str(signature_data.get("signature") or "")

    if not hmac.compare_digest(expected, actual):
        return False, "подпись экспорта не совпадает"

    return True, f"записей: {signature_data.get('records', '?')}"


def search(
    query: str,
    limit: int = 20,
    path: Path | None = None,
) -> list[dict]:
    """Поиск по событиям и полезной нагрузке аудита."""

    needle = str(query or "").strip().casefold()

    if not needle:
        return []

    source = Path(path or AUDIT_FILE)

    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    found = []

    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        text = json.dumps(entry, ensure_ascii=False).casefold()

        if needle in text:
            found.append(entry)

        if len(found) >= max(1, limit):
            break

    return found


def target_of(payload: dict) -> str:
    """Короткое и безопасное описание цели действия."""

    for key in ("path", "url", "command", "query"):
        value = payload.get(key)

        if value:
            return redact(str(value)).text[:200]

    return ""
