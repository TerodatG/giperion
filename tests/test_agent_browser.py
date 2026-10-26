# Giperion/tests/test_agent_browser.py                                 v001
# Браузер с JavaScript: настройки, проверки, воркер и реестр.

import json
import subprocess
import sys

import pytest

from terminal.core.agent import (
    browser_js,
    browser_worker,
    registry,
    settings,
    web,
)
from terminal.core.agent.loop_helpers import approval_key
from terminal.core.agent.protocol import ToolCall


@pytest.fixture(autouse=True)
def _settings_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )


def _enable(monkeypatch, available: bool = True) -> None:
    settings.set_browser_js_enabled(True)
    monkeypatch.setattr(browser_js, "available", lambda: available)
    monkeypatch.setattr(browser_js, "_robots_allows", lambda url: True)
    monkeypatch.setattr(browser_js, "_wait_rate", lambda url: None)


def _public(monkeypatch) -> None:
    monkeypatch.setattr(web, "validate_url", lambda url: url)
    monkeypatch.setattr(web, "host_of", lambda url: "example.com")
    monkeypatch.setattr(web, "is_public_host", lambda host: True)


def _worker(stdout: str, returncode: int = 0, stderr: str = ""):
    class Done:
        pass

    done = Done()
    done.stdout = stdout
    done.stderr = stderr
    done.returncode = returncode

    return done


def test_browser_js_setting_default_off() -> None:
    """Браузер с JS по умолчанию выключен и сохраняется."""

    assert settings.browser_js_enabled() is False

    settings.set_browser_js_enabled(True)

    assert settings.browser_js_enabled() is True


def test_read_requires_setting(tmp_path) -> None:
    """Пока галочка не включена, страница не открывается."""

    result = browser_js.read(tmp_path, "https://example.com")

    assert not result.ok
    assert "выключен" in result.text


def test_read_requires_playwright(tmp_path, monkeypatch) -> None:
    """Без пакета Playwright агент объясняет, что установить."""

    _enable(monkeypatch, available=False)

    result = browser_js.read(tmp_path, "https://example.com")

    assert not result.ok
    assert "Playwright не установлен" in result.text


def test_read_blocks_local_address(tmp_path, monkeypatch) -> None:
    """Локальные адреса запрещены, как у fetch_url."""

    _enable(monkeypatch)

    result = browser_js.read(tmp_path, "http://127.0.0.1/admin")

    assert not result.ok
    assert "локальную" in result.text or "приватную" in result.text


def test_read_parses_worker(tmp_path, monkeypatch) -> None:
    """Ответ воркера превращается в текст с заголовком."""

    _enable(monkeypatch)
    _public(monkeypatch)
    captured: dict = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs.get("env") or {}

        return _worker(
            json.dumps(
                {
                    "ok": True,
                    "url": "https://example.com/final",
                    "title": "Пример",
                    "text": "текст после JS",
                    "truncated": False,
                },
                ensure_ascii=False,
            )
        )

    monkeypatch.setattr(browser_js.subprocess, "run", fake_run)

    result = browser_js.read(tmp_path, "https://example.com", wait="#ready")

    assert result.ok
    assert "источник: https://example.com/final" in result.text
    assert "заголовок: Пример" in result.text
    assert "текст после JS" in result.text
    assert browser_js.WORKER in captured["command"]
    assert captured["env"]["PYTHONPATH"]

    request = json.loads(captured["command"][-1])

    assert request["url"] == "https://example.com"
    assert request["wait"] == "#ready"


def test_read_truncates_long_text(tmp_path, monkeypatch) -> None:
    """Длинная страница обрезается по лимиту."""

    _enable(monkeypatch)
    _public(monkeypatch)

    monkeypatch.setattr(
        browser_js.subprocess,
        "run",
        lambda command, **kwargs: _worker(
            json.dumps(
                {
                    "ok": True,
                    "url": "https://example.com",
                    "title": "",
                    "text": "х" * (browser_js.MAX_TEXT + 50),
                    "truncated": True,
                }
            )
        ),
    )

    result = browser_js.read(tmp_path, "https://example.com")

    assert result.ok
    assert "обрезана" in result.text


def test_read_timeout(tmp_path, monkeypatch) -> None:
    """Зависший браузер останавливается по таймауту."""

    _enable(monkeypatch)
    _public(monkeypatch)

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 80)

    monkeypatch.setattr(browser_js.subprocess, "run", fake_run)

    result = browser_js.read(tmp_path, "https://example.com", timeout=10)

    assert not result.ok
    assert "не ответил" in result.text


def test_read_without_json(tmp_path, monkeypatch) -> None:
    """Мусор в stdout не выдаётся за страницу."""

    _enable(monkeypatch)
    _public(monkeypatch)

    monkeypatch.setattr(
        browser_js.subprocess,
        "run",
        lambda command, **kwargs: _worker("Traceback: everything is broken"),
    )

    result = browser_js.read(tmp_path, "https://example.com")

    assert not result.ok
    assert "непонятный ответ" in result.text


def test_parse_takes_last_json_line() -> None:
    """Предупреждения перед JSON не мешают разбору."""

    data = browser_js._parse(
        'warning: something\n{"ok": true, "text": "x"}\n'
    )

    assert data == {"ok": True, "text": "x"}


def test_worker_clip_and_scheme() -> None:
    """Воркер режет текст и принимает только http/https."""

    text, truncated = browser_worker._clip(
        "а" * (browser_worker.MAX_TEXT + 5)
    )

    assert truncated is True
    assert len(text) == browser_worker.MAX_TEXT
    assert browser_worker._scheme_ok("https://example.com")
    assert not browser_worker._scheme_ok("file:///etc/passwd")
    assert not browser_worker._scheme_ok("javascript:alert(1)")


def test_tool_is_registered_and_rememberable() -> None:
    """browser_read — exec-инструмент с подтверждением по домену."""

    spec = registry.get_spec("browser_read")

    assert spec is not None
    assert spec.risk == "exec"
    assert spec.required == ("url",)

    key = approval_key(
        ToolCall("browser_read", {"url": "https://example.com/page"})
    )

    assert key == "web:example.com"


def test_registry_dispatches_browser(tmp_path, monkeypatch) -> None:
    """Реестр зовёт browser_js.read и проверяет аргументы."""

    calls: list[tuple] = []

    def fake_read(root, url, wait="", timeout=60):
        calls.append((root, url, wait))

        from terminal.core.agent.protocol import ToolResult

        return ToolResult(True, "страница")

    monkeypatch.setattr(browser_js, "read", fake_read)

    invalid = registry.execute(tmp_path, ToolCall("browser_read", {}))

    assert not invalid.ok

    result = registry.execute(
        tmp_path,
        ToolCall(
            "browser_read",
            {"url": "https://example.com", "wait": "#app"},
        ),
    )

    assert result.ok
    assert calls == [(tmp_path, "https://example.com", "#app")]


def test_worker_module_runs() -> None:
    """Воркер запускается как модуль и отвечает JSON без аргументов."""

    done = subprocess.run(
        [sys.executable, "-m", browser_worker.__name__],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )

    assert done.returncode == 1
    assert json.loads(done.stdout.strip())["ok"] is False

def test_sanitize_actions() -> None:
    """Действия фильтруются и ограничиваются по размеру."""

    actions = browser_js._sanitize_actions(
        [
            {"type": "click", "selector": "#go"},
            {"type": "fill", "selector": "#q", "text": "х" * 3000},
            {"type": "scroll", "pixels": 99999},
            {"type": "wait", "ms": -5},
            {"type": "bad"},
            {"type": "click"},
            "не объект",
        ]
    )

    assert [item["type"] for item in actions] == [
        "click",
        "fill",
        "scroll",
        "wait",
    ]
    assert len(actions[1]["text"]) == 2000
    assert actions[2]["pixels"] == 10_000
    assert actions[3]["ms"] == 0
    assert browser_js._sanitize_actions(None) == []


def test_robots_blocks_private_path(monkeypatch) -> None:
    """robots.txt запрещает закрытый раздел."""

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return b"User-agent: *\nDisallow: /private\n"

    browser_js._ROBOTS.clear()
    monkeypatch.setattr(
        browser_js.urllib.request,
        "urlopen",
        lambda request, timeout: Response(),
    )

    assert browser_js._robots_allows(
        "https://example.com/private/page"
    ) is False
    assert browser_js._robots_allows(
        "https://example.com/public"
    ) is True


def test_act_dispatches_actions(tmp_path, monkeypatch) -> None:
    """Реестр передаёт browser_act список действий."""

    calls: list[tuple] = []

    def fake_act(root, url, actions=None, wait="", shot=False, timeout=60):
        calls.append((root, url, actions, wait, shot))

        from terminal.core.agent.protocol import ToolResult

        return ToolResult(True, "готово")

    monkeypatch.setattr(browser_js, "act", fake_act)

    result = registry.execute(
        tmp_path,
        ToolCall(
            "browser_act",
            {
                "url": "https://example.com",
                "actions": [{"type": "click", "selector": "#go"}],
                "shot": True,
            },
        ),
    )

    assert result.ok
    assert calls[0][1] == "https://example.com"
    assert calls[0][2] == [{"type": "click", "selector": "#go"}]
    assert calls[0][4] is True

    invalid = registry.execute(
        tmp_path,
        ToolCall(
            "browser_act",
            {"url": "https://example.com", "actions": "click"},
        ),
    )

    assert not invalid.ok
