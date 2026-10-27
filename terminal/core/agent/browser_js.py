# Giperion/terminal/core/agent/browser_js.py                           v001
# Браузер с JavaScript: запуск Chromium в отдельном процессе.
# Последнее изменение: первый вариант — JSON-воркер, домены и таймауты.

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from urllib import robotparser

from config import BASE_DIR
from terminal.core.agent import settings, web
from terminal.core.agent.browser_fields import extra_values as _extra_values
from terminal.core.agent.protocol import ToolResult

MAX_TEXT = 12_000
MAX_ACTIONS = 12
DEFAULT_TIMEOUT = 60
MIN_INTERVAL = 1.5
ROBOTS_TTL = 300.0
ACTION_TYPES = {
    "click",
    "fill",
    "press",
    "hover",
    "select",
    "scroll",
    "wait",
    "wait_text",
    "wait_url",
    "new_tab",
    "switch_tab",
    "close_tab",
    "goto",
    "back",
    "download",
}
WORKER = "terminal.core.agent.browser_worker"
ENV_KEYS = (
    "PATH",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
)


def available() -> bool:
    """Установлен ли пакет Playwright."""

    return importlib.util.find_spec("playwright") is not None


def _env() -> dict[str, str]:
    """Минимальное окружение воркера с PYTHONPATH проекта."""

    env = {
        key: os.environ[key]
        for key in ENV_KEYS
        if key in os.environ
    }
    env["PYTHONPATH"] = str(BASE_DIR)
    env["PYTHONIOENCODING"] = "utf-8"

    return env


def _parse(stdout: str) -> dict:
    """Последняя JSON-строка в выводе воркера."""

    for line in reversed(str(stdout or "").splitlines()):
        text = line.strip()

        if not text.startswith("{"):
            continue

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue

        if isinstance(data, dict):
            return data

    raise ValueError("воркер не вернул JSON")


def _check(url: str) -> str:
    """Проверяет адрес теми же правилами, что и fetch_url."""

    clean = web.validate_url(url)
    host = web.host_of(clean)

    if not web.is_public_host(host):
        raise web.WebError(
            "Адрес ведёт в локальную или приватную сеть — запрещено."
        )

    if not web.egress_allowed(host):
        raise web.WebError(
            f"Домен «{host}» не входит в общий allowlist."
        )

    return clean


def _badge(data: dict, clean: str) -> str:
    """Заголовок ответа: источник и заголовок страницы."""

    final = str(data.get("url") or clean)
    title = str(data.get("title") or "").strip()
    header = f"источник: {final}"

    if title:
        header += f"\nзаголовок: {title}"

    return header


def _action_values(
    item: dict,
    kind: str,
    selector: str,
) -> dict | None:
    """Поля одного действия; None — действие пропускается."""

    action = {"type": kind}

    if kind in ("click", "fill", "press", "hover", "select", "download"):
        if not selector:
            return None

        action["selector"] = selector
    elif kind == "goto":
        target = str(item.get("url") or "").strip()[:2048]
        scheme = urllib.parse.urlsplit(target).scheme

        if not target or scheme not in ("http", "https"):
            return None

        action["url"] = target

    if not _extra_values(action, item, kind):
        return None

    return action


def _sanitize_actions(value) -> list[dict]:
    """Оставляет до двенадцати понятных действий браузера."""

    if not isinstance(value, list):
        return []

    actions = []

    for item in value[:MAX_ACTIONS]:
        if not isinstance(item, dict):
            continue

        kind = str(item.get("type") or "").strip().lower()

        if kind not in ACTION_TYPES:
            continue

        selector = str(item.get("selector") or "").strip()[:200]
        action = _action_values(item, kind, selector)

        if action is not None:
            actions.append(action)

    return actions


_ROBOTS: dict[str, tuple[float, robotparser.RobotFileParser]] = {}
_LAST_HIT: dict[str, float] = {}


def _robots_allows(url: str) -> bool:
    """Соблюдает robots.txt домена (если файл доступен)."""

    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return True

    origin = f"{parsed.scheme}://{parsed.netloc}"
    now = time.monotonic()
    cached = _ROBOTS.get(origin)

    if cached is not None and now - cached[0] < ROBOTS_TTL:
        parser = cached[1]
    else:
        parser = robotparser.RobotFileParser()

        try:
            request = urllib.request.Request(
                origin + "/robots.txt",
                headers={"User-Agent": "GiperionBot/1.0"},
            )

            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read(200_000).decode(
                    "utf-8",
                    errors="replace",
                )

            parser.parse(body.splitlines())
        except Exception:  # noqa: BLE001 — нет robots.txt, значит можно
            parser.parse([])

        _ROBOTS[origin] = (now, parser)

    try:
        return parser.can_fetch("*", url)
    except Exception:  # noqa: BLE001 — сомнительный robots.txt
        return True


def _wait_rate(url: str) -> None:
    """Не чаще одного запроса к домену в MIN_INTERVAL секунд."""

    try:
        host = urllib.parse.urlsplit(url).netloc
    except ValueError:
        return

    now = time.monotonic()
    delay = MIN_INTERVAL - (now - _LAST_HIT.get(host, 0.0))

    if delay > 0:
        time.sleep(min(3.0, delay))

    _LAST_HIT[host] = time.monotonic()


def _shot_path(root: Path, url: str) -> Path:
    """Путь для скриншота под data/agent_browser."""

    base = Path(root).resolve()
    digest = hashlib.sha1(str(url).encode("utf-8")).hexdigest()[:10]

    return (
        base
        / "data"
        / "agent_browser"
        / f"{int(time.time())}-{digest}.png"
    )


def _invoke_worker(
    root: Path,
    request: dict,
    seconds: int,
) -> tuple[dict | None, str]:
    """Одноразовый воркер: запуск Chromium на один запрос."""

    if str(request.get("cmd") or "open") != "open":
        return None, "Текущая страница доступна только в сессии браузера."

    command = [
        sys.executable,
        "-m",
        WORKER,
        json.dumps(request, ensure_ascii=False),
    ]

    try:
        done = subprocess.run(
            command,
            cwd=str(Path(root).resolve()),
            env=_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=seconds + 20,
        )
    except subprocess.TimeoutExpired:
        return None, f"Браузер не ответил за {seconds + 20} с."
    except OSError as error:
        return None, f"Не удалось запустить браузер: {error}"

    if not str(done.stdout or "").strip():
        tail = str(done.stderr or "").strip()[-400:]

        return None, (
            "Браузер завершился без ответа"
            + (f": {tail}" if tail else ".")
        )

    try:
        data = _parse(done.stdout)
    except ValueError:
        return None, "Браузер вернул непонятный ответ."

    if not data.get("ok"):
        return None, (
            "Не удалось открыть страницу: "
            + str(data.get("error") or "неизвестная ошибка")
        )

    return data, ""


def _invoke(
    root: Path,
    request: dict,
    seconds: int,
) -> tuple[dict | None, str]:
    """Пробует сессию на задачу, иначе поднимает разовый браузер."""

    if settings.browser_session_enabled():
        try:
            from terminal.core.agent import browser_session

            session = browser_session.current(Path(root))
            data = session.request(
                str(request.get("cmd") or "open"),
                timeout=seconds,
                **{
                    key: value
                    for key, value in request.items()
                    if key != "cmd"
                },
            )

            return data, ""
        except Exception:  # noqa: BLE001 — откат к разовому запуску
            from terminal.core.agent import browser_session

            browser_session.close_current()

    return _invoke_worker(root, request, seconds)


def close_session() -> None:
    """Закрывает браузер текущего потока."""

    from terminal.core.agent import browser_session

    browser_session.close_current()


def _check_links(actions: list[dict]) -> None:
    """Проверяет адреса переходов внутри серии действий."""

    for action in actions:
        if action.get("type") not in ("goto", "new_tab"):
            continue

        clean = _check(str(action.get("url") or ""))
        action["url"] = clean


def _answer(
    data: dict,
    clean: str,
    root: Path,
    target: Path | None,
) -> ToolResult:
    """Формирует текст ответа и путь скриншота."""

    text = str(data.get("text") or "").strip()
    body = _badge(data, clean) + "\n\n" + text[:MAX_TEXT]

    if data.get("truncated") or len(text) > MAX_TEXT:
        body += "\n\n… страница обрезана по лимиту."

    if target is not None and target.exists():
        try:
            shown = target.relative_to(Path(root).resolve())
        except ValueError:
            shown = target

        body += f"\n\nскриншот: {Path(shown).as_posix()}"

    downloads = data.get("downloads") or []

    if downloads:
        shown_downloads = []

        for item in downloads:
            try:
                shown_item = Path(item).resolve().relative_to(
                    Path(root).resolve()
                )
            except (OSError, ValueError):
                shown_item = Path(item)

            shown_downloads.append(Path(shown_item).as_posix())

        body += "\n\nфайлы: " + ", ".join(shown_downloads)

    pdf = str(data.get("download_text") or "").strip()

    if pdf:
        body += "\n\nТекст PDF:\n" + pdf[:MAX_TEXT]

    return ToolResult(True, body)


def _run(
    root: Path,
    url: str,
    *,
    wait: str,
    timeout: int,
    actions: list[dict],
    shot: bool,
    full_page: bool = False,
) -> ToolResult:
    """Общий путь: проверки, robots, сессия/воркер и разбор ответа."""

    if not settings.browser_js_enabled():
        return ToolResult(
            False,
            "Браузер с JavaScript выключен: включи «Браузер с JavaScript "
            "(Playwright)» в окне «Провайдер…».",
        )

    if not available():
        return ToolResult(
            False,
            "Playwright не установлен: python -m pip install playwright "
            "и python -m playwright install chromium.",
        )

    current = str(url or "").strip().lower() in (
        "",
        "current",
        "текущая",
    )

    if current and not settings.browser_session_enabled():
        return ToolResult(
            False,
            "Текущая страница доступна только в сессии браузера.",
        )

    if current:
        clean = ""
        command = "act" if actions else "read"
        target = _shot_path(root, "current") if shot else None
    else:
        try:
            clean = _check(url)
        except web.WebError as error:
            return ToolResult(False, str(error))

        if not _robots_allows(clean):
            return ToolResult(
                False,
                "robots.txt запрещает открывать этот адрес агенту.",
            )

        _wait_rate(clean)
        command = "open"
        target = _shot_path(root, clean) if shot else None

    seconds = min(120, max(5, int(timeout or DEFAULT_TIMEOUT)))
    request = {
        "cmd": command,
        "url": clean,
        "wait": str(wait or ""),
        "timeout_ms": seconds * 1000,
        "actions": list(actions),
        "full_page": bool(full_page),
    }

    if target is not None:
        request["shot_path"] = str(target)

    if any(
        action.get("type") == "download"
        for action in actions
    ):
        request["download_dir"] = str(
            Path(root).resolve()
            / "data"
            / "agent_browser"
            / "downloads"
        )

    data, error = _invoke(root, request, seconds)

    if data is None:
        return ToolResult(False, error)

    return _answer(data, clean, root, target)


def read(
    root: Path,
    url: str,
    wait: str = "",
    timeout: int = DEFAULT_TIMEOUT,
) -> ToolResult:
    """Открывает страницу в Chromium и возвращает текст после JavaScript."""

    return _run(
        root,
        url,
        wait=wait,
        timeout=timeout,
        actions=[],
        shot=False,
    )


def act(
    root: Path,
    url: str,
    actions: list | None = None,
    wait: str = "",
    shot: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    full_page: bool = False,
) -> ToolResult:
    """Открывает страницу, выполняет действия и возвращает текст."""

    clean_actions = _sanitize_actions(actions)

    try:
        _check_links(clean_actions)
    except web.WebError as error:
        return ToolResult(False, str(error))

    return _run(
        root,
        url,
        wait=wait,
        timeout=timeout,
        actions=clean_actions,
        shot=bool(shot),
        full_page=bool(full_page),
    )
