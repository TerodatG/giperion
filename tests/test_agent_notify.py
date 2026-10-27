# Giperion/tests/test_agent_notify.py                                  v001
# Вебхуки: адрес, редакция секретов и отказ без URL.

import json

from terminal.core.agent import notify


def test_without_url_does_nothing(monkeypatch) -> None:
    """Без GIPERION_WEBHOOK_URL отправка не выполняется."""

    monkeypatch.delenv("GIPERION_WEBHOOK_URL", raising=False)

    assert notify.send("готово") is False


def test_webhook_redacts_secret(monkeypatch) -> None:
    """Вебхук получает JSON с вырезанным секретом."""

    sent = {}

    class Response:
        def read(self, limit=0):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=0):
        sent["url"] = request.full_url
        sent["body"] = json.loads(request.data.decode("utf-8"))

        return Response()

    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)

    assert notify.send(
        "ключ sk-1234567890abcdef",
        "https://example.com/hook",
    )
    assert sent["url"] == "https://example.com/hook"
    assert "sk-1234567890abcdef" not in sent["body"]["text"]
    assert "[скрыто]" in sent["body"]["text"]


def test_bad_scheme_is_rejected(monkeypatch) -> None:
    """ftp и file не отправляются."""

    assert notify.send("текст", "file:///etc/passwd") is False
