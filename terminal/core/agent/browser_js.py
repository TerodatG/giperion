# Giperion/terminal/core/agent/browser_js.py                           v001
# Браузер с JavaScript: запуск Chromium в отдельном процессе.
# Последнее изменение: первый вариант — JSON-воркер, домены и таймауты.

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from config import BASE_DIR
from terminal.core.agent import settings, web
from terminal.core.agent.protocol import ToolResult

MAX_TEXT = 12_000
DEFAULT_TIMEOUT = 60
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

    if not web.is_public_host(web.host_of(clean)):
        raise web.WebError(
            "Адрес ведёт в локальную или приватную сеть — запрещено."
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


def read(
    root: Path,
    url: str,
    wait: str = "",
    timeout: int = DEFAULT_TIMEOUT,
) -> ToolResult:
    """Открывает страницу в Chromium и возвращает текст после JavaScript."""

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

    seconds = min(120, max(5, int(timeout or DEFAULT_TIMEOUT)))
    request = {
        "url": clean,
        "wait": str(wait or ""),
        "timeout_ms": seconds * 1000,
    }
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
        return ToolResult(
            False,
            f"Браузер не ответил за {seconds + 20} с.",
        )
    except OSError as error:
        return ToolResult(False, f"Не удалось запустить браузер: {error}")

    if not str(done.stdout or "").strip():
        tail = str(done.stderr or "").strip()[-400:]

        return ToolResult(
            False,
            "Браузер завершился без ответа"
            + (f": {tail}" if tail else "."),
        )

    try:
        data = _parse(done.stdout)
    except ValueError:
        return ToolResult(False, "Браузер вернул непонятный ответ.")

    if not data.get("ok"):
        return ToolResult(
            False,
            "Не удалось открыть страницу: "
            + str(data.get("error") or "неизвестная ошибка"),
        )

    text = str(data.get("text") or "").strip()
    body = _badge(data, clean) + "\n\n" + text[:MAX_TEXT]

    if data.get("truncated") or len(text) > MAX_TEXT:
        body += "\n\n… страница обрезана по лимиту."

    return ToolResult(True, body)
