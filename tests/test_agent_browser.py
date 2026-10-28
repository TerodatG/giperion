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
    monkeypatch.setattr(
        settings,
        "browser_session_enabled",
        lambda: False,
    )


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

    from terminal.core.agent import browser_page

    text, truncated = browser_worker._clip(
        "а" * (browser_page.MAX_TEXT + 5)
    )

    assert truncated is True
    assert len(text) == browser_page.MAX_TEXT
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

    def fake_act(
        root,
        url,
        actions=None,
        wait="",
        shot=False,
        timeout=60,
        full_page=False,
    ):
        calls.append((root, url, actions, wait, shot, full_page))

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

def test_sanitize_new_actions() -> None:
    """Переходы, назад, наведение и выбор поддерживаются."""

    actions = browser_js._sanitize_actions(
        [
            {"type": "goto", "url": "https://example.com/page"},
            {"type": "back"},
            {"type": "hover", "selector": "#menu"},
            {"type": "select", "selector": "#city", "value": "msk"},
            {"type": "goto", "url": "file:///etc/passwd"},
            {"type": "hover"},
        ]
    )

    assert [item["type"] for item in actions] == [
        "goto",
        "back",
        "hover",
        "select",
    ]
    assert actions[0]["url"] == "https://example.com/page"
    assert actions[3]["value"] == "msk"


def test_goto_links_are_checked(monkeypatch) -> None:
    """Переход внутри действий проходит проверку домена."""

    def fake_check(url):
        if "python.org" in url:
            raise web.WebError("домен запрещён")

        return url

    monkeypatch.setattr(browser_js, "_check", fake_check)

    actions = [{"type": "goto", "url": "https://example.com/x"}]

    browser_js._check_links(actions)

    assert actions[0]["url"] == "https://example.com/x"

    with pytest.raises(web.WebError):
        browser_js._check_links(
            [{"type": "goto", "url": "https://python.org/"}]
        )

def test_invoke_uses_session(tmp_path, monkeypatch) -> None:
    """При включённой сессии запрос идёт в неё."""

    from terminal.core.agent import browser_session, settings

    monkeypatch.setattr(
        settings,
        "browser_session_enabled",
        lambda: True,
    )

    class FakeSession:
        def request(self, command, timeout=90, **params):
            assert command == "open"

            return {
                "ok": True,
                "url": params["url"],
                "title": "",
                "text": "из сессии",
                "truncated": False,
                "shot": "",
            }

    monkeypatch.setattr(
        browser_session,
        "current",
        lambda root: FakeSession(),
    )

    data, error = browser_js._invoke(
        tmp_path,
        {"url": "https://example.com"},
        5,
    )

    assert not error
    assert data["text"] == "из сессии"


def test_invoke_falls_back(tmp_path, monkeypatch) -> None:
    """Сбой сессии откатывается на разовый браузер."""

    from terminal.core.agent import browser_session, settings

    monkeypatch.setattr(
        settings,
        "browser_session_enabled",
        lambda: True,
    )

    def broken(root):
        raise browser_session.BrowserSessionError("нет сессии")

    monkeypatch.setattr(browser_session, "current", broken)
    monkeypatch.setattr(
        browser_session,
        "close_current",
        lambda: None,
    )
    monkeypatch.setattr(
        browser_js,
        "_invoke_worker",
        lambda root, request, seconds: (
            {"ok": True, "text": "разово"},
            "",
        ),
    )

    data, error = browser_js._invoke(
        tmp_path,
        {"url": "https://example.com"},
        5,
    )

    assert not error
    assert data["text"] == "разово"

def test_current_page_uses_session(tmp_path, monkeypatch) -> None:
    """url=current читает открытую страницу без перехода."""

    from terminal.core.agent import browser_session, settings

    monkeypatch.setattr(settings, "browser_js_enabled", lambda: True)
    monkeypatch.setattr(settings, "browser_session_enabled", lambda: True)
    monkeypatch.setattr(browser_js, "available", lambda: True)

    calls: list[str] = []

    class FakeSession:
        def request(self, command, timeout=90, **params):
            calls.append(command)

            return {
                "ok": True,
                "url": "https://example.com/next",
                "title": "next",
                "text": "текущая страница",
                "truncated": False,
                "shot": "",
            }

    monkeypatch.setattr(
        browser_session,
        "current",
        lambda root: FakeSession(),
    )

    result = browser_js.read(tmp_path, "current")

    assert result.ok
    assert "текущая страница" in result.text
    assert calls == ["read"]

    act = browser_js.act(
        tmp_path,
        "current",
        actions=[{"type": "click", "selector": "#next"}],
    )

    assert act.ok
    assert calls == ["read", "act"]


def test_current_needs_session(tmp_path, monkeypatch) -> None:
    """Без сессии current не открывается разовым браузером."""

    from terminal.core.agent import settings

    monkeypatch.setattr(settings, "browser_js_enabled", lambda: True)
    monkeypatch.setattr(settings, "browser_session_enabled", lambda: False)
    monkeypatch.setattr(browser_js, "available", lambda: True)

    result = browser_js.read(tmp_path, "current")

    assert not result.ok
    assert "сессии" in result.text

def test_browser_session_setting() -> None:
    """Сессия браузера включена по умолчанию и сохраняется."""

    assert settings.browser_session_enabled() is True

    settings.set_browser_session_enabled(False)

    assert settings.browser_session_enabled() is False


def test_browser_pool_reuses_session(tmp_path, monkeypatch) -> None:
    """Живая сессия возвращается в пул и переиспользуется."""

    from terminal.core.agent import browser_session

    created = []
    closed = []

    class FakeSession:
        def __init__(self, root):
            self.root = root
            self.process = object()
            created.append(self)

        def alive(self):
            return True

        def close(self):
            closed.append(self)

    monkeypatch.setattr(
        browser_session,
        "BrowserSession",
        FakeSession,
    )
    browser_session.close_all()

    first = browser_session.current(tmp_path)
    browser_session.release_current()
    second = browser_session.current(tmp_path)

    assert first is second
    assert len(created) == 1

    browser_session.close_current()

    assert closed == [first]
    browser_session.close_all()

def test_download_action_is_sanitized() -> None:
    """Скачивание требует селектор."""

    actions = browser_js._sanitize_actions(
        [
            {"type": "download", "selector": "a.file"},
            {"type": "download"},
        ]
    )

    assert actions == [{"type": "download", "selector": "a.file"}]


def test_download_paths_are_shown(tmp_path) -> None:
    """Путь скачанного файла попадает в ответ."""

    target = tmp_path / "data" / "agent_browser" / "downloads" / "a.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"%PDF")

    data = {
        "ok": True,
        "url": "https://example.com/file",
        "title": "",
        "text": "",
        "truncated": False,
        "shot": "",
        "downloads": [str(target)],
        "download_text": "текст из PDF",
    }

    result = browser_js._answer(
        data,
        "https://example.com/file",
        tmp_path,
        None,
    )

    assert result.ok
    assert "файлы:" in result.text
    assert "a.pdf" in result.text
    assert "текст из PDF" in result.text


def test_wait_actions_are_sanitized() -> None:
    """Ожидания по тексту и URL требуют полезной нагрузки."""

    actions = browser_js._sanitize_actions(
        [
            {"type": "wait_text", "text": "Готово"},
            {"type": "wait_text"},
            {"type": "wait_url", "url": "/success"},
            {"type": "wait_url"},
        ]
    )

    assert actions == [
        {"type": "wait_text", "text": "Готово"},
        {"type": "wait_url", "url": "/success"},
    ]


def test_profile_is_loaded_and_saved(tmp_path, monkeypatch) -> None:
    """Cookies подхватываются из профиля и сохраняются обратно."""

    from terminal.core.agent import browser_profile, browser_worker

    profile = tmp_path / "profile.json"
    profile.write_text('{"cookies": []}', encoding="utf-8")
    monkeypatch.setattr(browser_profile, "PROFILE_FILE", profile)
    seen = {}

    class Page:
        def set_default_timeout(self, value):
            pass

    class Context:
        def route(self, pattern, handler):
            pass

        def new_page(self):
            return Page()

        def storage_state(self, path):
            seen["saved"] = path

    class Browser:
        def new_context(self, **kwargs):
            seen.update(kwargs)

            return Context()

    class Chromium:
        def launch(self, **kwargs):
            return Browser()

    class Runtime:
        chromium = Chromium()

    browser_worker._new_page(Runtime())

    assert seen["storage_state"] == str(profile)

    browser_profile.save_profile(Context())

    assert seen["saved"] == str(profile)


def test_tab_actions_are_sanitized() -> None:
    """Вкладки: новая, переключение и закрытие."""

    actions = browser_js._sanitize_actions(
        [
            {"type": "new_tab", "url": "https://example.com/a"},
            {"type": "new_tab", "url": "file:///etc/passwd"},
            {"type": "switch_tab", "index": 50},
            {"type": "close_tab"},
        ]
    )

    assert actions == [
        {"type": "new_tab", "url": "https://example.com/a"},
        {"type": "switch_tab", "index": 20},
        {"type": "close_tab"},
    ]


def test_run_actions_switches_tabs() -> None:
    """new_tab и switch_tab меняют текущую страницу."""

    from terminal.core.agent import browser_worker

    class Page:
        def __init__(self, context) -> None:
            self.context = context
            self.goto_calls = []

        def set_default_timeout(self, value):
            pass

        def goto(self, url, **kwargs):
            self.goto_calls.append(url)

        def wait_for_timeout(self, value):
            pass

    class Context:
        def __init__(self) -> None:
            self.first = Page(self)
            self.pages = [self.first]

        def new_page(self):
            page = Page(self)
            self.pages.append(page)

            return page

    context = Context()
    first = context.first
    second = browser_worker._run_actions(
        first,
        [{"type": "new_tab", "url": "https://example.com/a"}],
        1_000,
    )

    assert second is context.pages[1]
    assert second.goto_calls == ["https://example.com/a"]

    back = browser_worker._run_actions(
        second,
        [{"type": "switch_tab", "index": 0}],
        1_000,
    )

    assert back is first


def test_websocket_guard_blocks_private_networks(monkeypatch) -> None:
    """WS-фильтр закрывает локальные адреса и пропускает публичные."""

    from types import SimpleNamespace

    from terminal.core.agent import browser_worker, web

    closed = []
    opened = []

    class Route:
        def __init__(self, url: str) -> None:
            self.url = url
            self.request = SimpleNamespace(url=url)

        def close(self):
            closed.append(self.url)

        def connect_to_server(self):
            opened.append(self.url)

    monkeypatch.setattr(
        web,
        "is_public_host",
        lambda host: host == "example.com",
    )

    browser_worker._guard_ws(Route("wss://example.com/socket"))
    browser_worker._guard_ws(Route("wss://127.0.0.1/socket"))

    assert opened == ["wss://example.com/socket"]
    assert closed == ["wss://127.0.0.1/socket"]


def test_browser_pins_initial_host(monkeypatch) -> None:
    """Chromium получает MAP хост → проверенный IP."""

    from terminal.core.agent import browser_worker, web

    monkeypatch.setattr(
        web,
        "resolve_public",
        lambda host: ("93.184.216.34",),
    )

    args = browser_worker._resolver_args("https://example.com/page")

    assert args == [
        "--host-resolver-rules=MAP example.com 93.184.216.34"
    ]


def test_act_records_scenario(tmp_path, monkeypatch) -> None:
    """Успешный browser_act сохраняет JSON-сценарий внутри проекта."""

    from terminal.core.agent.protocol import ToolResult

    monkeypatch.setattr(
        browser_js,
        "_run",
        lambda *args, **kwargs: ToolResult(True, "ok"),
    )

    result = browser_js.act(
        tmp_path,
        "https://example.com/login",
        actions=[{"type": "click", "selector": "#go"}],
        wait="#form",
        record="data/scenario.json",
    )

    assert result.ok
    text = (tmp_path / "data" / "scenario.json").read_text(
        encoding="utf-8"
    )
    assert "example.com/login" in text
    assert "#go" in text


def test_record_outside_project_is_ignored(tmp_path, monkeypatch) -> None:
    """Сценарий нельзя записать за пределы проекта."""

    from terminal.core.agent.protocol import ToolResult

    monkeypatch.setattr(
        browser_js,
        "_run",
        lambda *args, **kwargs: ToolResult(True, "ok"),
    )

    outside = tmp_path.parent / "evil.json"
    browser_js.act(
        tmp_path,
        "https://example.com",
        actions=[],
        record=str(outside),
    )

    assert not outside.exists()
