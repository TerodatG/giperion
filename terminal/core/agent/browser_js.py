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
from terminal.core.agent.protocol import ToolResult

MAX_TEXT = 12_000
MAX_ACTIONS = 10
DEFAULT_TIMEOUT = 60
MIN_INTERVAL = 1.5
ROBOTS_TTL = 300.0
ACTION_TYPES = {"click", "fill", "press", "scroll", "wait"}
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


def _sanitize_actions(value) -> list[dict]:
    """Оставляет до десяти понятных действий браузера."""

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
        action = {"type": kind}

        if kind in ("click", "fill", "press") and not selector:
            continue

        if selector:
            action["selector"] = selector

        if kind == "fill":
            action["text"] = str(item.get("text") or "")[:2000]
        elif kind == "press":
            action["key"] = str(item.get("key") or "Enter")[:30]
        elif kind == "scroll":
            action["pixels"] = max(
                -10_000,
                min(10_000, int(item.get("pixels") or 800)),
            )
        elif kind == "wait":
            action["ms"] = max(
                0,
                min(10_000, int(item.get("ms") or 500)),
            )

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


def _invoke(
    root: Path,
    request: dict,
    seconds: int,
) -> tuple[dict | None, str]:
    """Запускает воркер и разбирает его ответ."""

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

    return ToolResult(True, body)


def _run(
    root: Path,
    url: str,
    *,
    wait: str,
    timeout: int,
    actions: list[dict],
    shot: bool,
) -> ToolResult:
    """Общий путь: проверки, robots, воркер и разбор ответа."""

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
    seconds = min(120, max(5, int(timeout or DEFAULT_TIMEOUT)))
    target = _shot_path(root, clean) if shot else None
    request = {
        "url": clean,
        "wait": str(wait or ""),
        "timeout_ms": seconds * 1000,
        "actions": list(actions),
    }

    if target is not None:
        request["shot_path"] = str(target)

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
) -> ToolResult:
    """Открывает страницу, выполняет действия и возвращает текст."""

    clean_actions = _sanitize_actions(actions)

    return _run(
        root,
        url,
        wait=wait,
        timeout=timeout,
        actions=clean_actions,
        shot=bool(shot),
    )
