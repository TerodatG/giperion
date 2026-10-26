# Giperion/tests/test_agent_audit.py                                   v001
# Аудит: хеш-цепочка, подмена и короткое описание цели.

import json

import pytest

from terminal.core.agent import audit


@pytest.fixture(autouse=True)
def _file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        audit,
        "AUDIT_FILE",
        tmp_path / "audit.jsonl",
    )


def test_chain_and_tail() -> None:
    """Записи связываются хешем, tail отдаёт последние."""

    audit.record("start", {"task": "найди файл"})
    audit.record("approval", {"tool": "read_file"})

    ok, message = audit.verify()

    assert ok
    assert "2" in message

    entries = audit.tail(1)

    assert entries[0]["event"] == "approval"
    assert entries[0]["prev"] == audit.tail(2)[0]["hash"]


def test_tamper_is_detected() -> None:
    """Изменение полезной нагрузки ломает цепочку."""

    audit.record("start", {"task": "одна"})
    audit.record("finish", {"ok": True})

    path = audit.AUDIT_FILE
    lines = path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[1])
    entry["payload"] = {"ok": False}
    lines[1] = json.dumps(entry, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, message = audit.verify()

    assert not ok
    assert "подмена" in message


def test_broken_previous_hash() -> None:
    """Разрыв ссылки на предыдущую запись виден."""

    audit.record("start", {})

    path = audit.AUDIT_FILE
    entry = json.loads(path.read_text(encoding="utf-8").strip())
    entry["prev"] = "1" * 64
    path.write_text(
        json.dumps(entry, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    ok, message = audit.verify()

    assert not ok
    assert "разорвана" in message


def test_target_redacts_secret() -> None:
    """Цель действия не хранит секрет целиком."""

    target = audit.target_of(
        {"command": "curl -H 'Authorization: Bearer sk-secret-123456'"}
    )

    assert "sk-secret-123456" not in target
    assert target


def test_empty_journal_is_valid() -> None:
    """Отсутствие журнала — не ошибка."""

    ok, message = audit.verify()

    assert ok
    assert "пуст" in message
