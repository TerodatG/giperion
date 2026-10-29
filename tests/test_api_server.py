# Giperion/tests/test_api_server.py                                    v001
# HTTP-API терминала: токен, лимиты, запуск задачи и SDK.

import json
import threading
import time

import pytest

from terminal.api import api_config as config
from terminal.api import server, service
from terminal.api.client import Client, ClientError

TOKEN = "test-token"


class FakeBrain:
    """Мозг-заглушка: один инструмент, затем ответ."""

    native = False
    messages_mode = False

    def __init__(self) -> None:
        self.calls = 0

    def decide(self, prompt: str) -> str:
        self.calls += 1

        if self.calls == 1:
            return json.dumps(
                {
                    "action": "tool",
                    "tool": "list_dir",
                    "args": {"path": "."},
                }
            )

        return json.dumps({"action": "answer", "text": "готово"})


@pytest.fixture()
def api(tmp_path, monkeypatch):
    """Поднимает сервер на свободном порту с известным токеном."""

    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setenv(config.TOKEN_ENV, TOKEN)
    monkeypatch.setenv(config.ROOTS_ENV, str(tmp_path))
    monkeypatch.setattr(config, "JOURNAL", tmp_path / "api_calls.jsonl")
    monkeypatch.setattr(service, "build_brain", lambda: FakeBrain())

    server._RATE.clear()

    httpd = server.make_server("127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    host, port = httpd.server_address[:2]

    yield f"http://{host}:{port}", project

    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _client(api, token: str = TOKEN) -> Client:
    url, _ = api

    return Client(base_url=url, token=token, timeout=30)


def test_health_needs_no_token(api) -> None:
    """Проверка живости доступна без токена."""

    assert _client(api, token="").health() == {"ok": True}


def test_version_requires_token(api) -> None:
    """Без верного токена остальные пути закрыты."""

    with pytest.raises(ClientError) as error:
        _client(api, token="wrong-token").version()

    assert "401" in str(error.value)


def test_version_and_tools(api) -> None:
    """С токеном отдаются версия и список инструментов."""

    client = _client(api)

    version = client.version()

    assert version["version"]
    assert version["tools"] > 0
    assert "read_file" in client.tools()


def test_run_executes_task(api) -> None:
    """Задача выполняется и возвращает трейс."""

    _, project = api

    result = _client(api).run("что в папке?", project=str(project))

    assert result["ok"] is True
    assert result["answer"] == "готово"
    assert any(
        "list_dir" in step["title"] or step["kind"] == "tool"
        for step in result["steps"]
    )


def test_run_rejects_empty_task(api) -> None:
    """Пустая задача — ошибка 400."""

    _, project = api

    with pytest.raises(ClientError) as error:
        _client(api).run("   ", project=str(project))

    assert "400" in str(error.value)


def test_run_rejects_foreign_project(api, tmp_path) -> None:
    """Проект вне разрешённых каталогов не запускается."""

    outside = tmp_path.parent / "outside-project"
    outside.mkdir(exist_ok=True)

    with pytest.raises(ClientError) as error:
        _client(api).run("задача", project=str(outside))

    assert "400" in str(error.value)


def test_unknown_path_returns_404(api) -> None:
    """Неизвестный путь — 404."""

    with pytest.raises(ClientError) as error:
        _client(api)._request("GET", "/nope")

    assert "404" in str(error.value)


def test_async_run_is_polled_to_done(api) -> None:
    """Фоновый прогон доступен по id и доходит до результата."""

    _, project = api
    client = _client(api)

    started = client._request(
        "POST",
        "/run",
        {"task": "что в папке?", "project": str(project), "wait": False},
    )

    assert started["id"]
    run_id = started["id"]
    state = {}

    for _ in range(100):
        state = client._request("GET", f"/run/{run_id}")

        if state["status"] in ("done", "failed", "cancelled"):
            break

        time.sleep(0.05)

    assert state["status"] == "done"
    assert state["result"]["answer"] == "готово"


def test_unknown_run_returns_404(api) -> None:
    """Неизвестный id прогона — 404."""

    with pytest.raises(ClientError) as error:
        _client(api)._request("GET", "/run/nope")

    assert "404" in str(error.value)


def test_calls_are_journalled(api, tmp_path) -> None:
    """Каждый вызов попадает в журнал."""

    _client(api).version()

    journal = tmp_path / "api_calls.jsonl"
    lines: list[dict] = []

    for _ in range(50):
        if journal.is_file():
            lines = [
                json.loads(line)
                for line in journal.read_text(encoding="utf-8").splitlines()
            ]

            if lines:
                break

        time.sleep(0.02)

    assert any(item["path"] == "/version" for item in lines)


def test_rate_limit_returns_429(api, monkeypatch) -> None:
    """Превышение лимита частоты даёт 429."""

    monkeypatch.setattr(server, "RATE_LIMIT", 2)

    client = _client(api)
    client.version()
    client.version()

    with pytest.raises(ClientError) as error:
        client.version()

    assert "429" in str(error.value)
