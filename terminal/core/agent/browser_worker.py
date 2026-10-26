# Giperion/terminal/core/agent/browser_worker.py                      v001
# Дочерний процесс: рендер страницы в headless Chromium.
# Последнее изменение: первый вариант — JSON в argv, текст и заголовок.

import json
import sys
import urllib.parse

MAX_TEXT = 12_000
SETTLE_MS = 1200


def _request() -> dict:
    """Разбирает JSON-аргумент командной строки."""

    if len(sys.argv) < 2:
        return {}

    try:
        data = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        return {}

    return data if isinstance(data, dict) else {}


def _scheme_ok(url: str) -> bool:
    """Только http и https — никаких file:, data: и javascript:."""

    try:
        scheme = urllib.parse.urlsplit(str(url or "")).scheme
    except ValueError:
        return False

    return scheme in ("http", "https")


def _clip(text: str) -> tuple[str, bool]:
    """Обрезает текст страницы по лимиту."""

    value = str(text or "")

    return value[:MAX_TEXT], len(value) > MAX_TEXT


def _guard(route) -> None:
    """Не пускает браузер в локальную сеть даже из JS-запросов."""

    from terminal.core.agent import web

    try:
        request_url = route.request.url
        host = urllib.parse.urlsplit(request_url).hostname or ""
    except Exception:  # noqa: BLE001 — подозрительный запрос
        route.abort()
        return

    if not _scheme_ok(request_url) or not web.is_public_host(host):
        route.abort()
        return

    route.continue_()


def _act_goto(page, action: dict, timeout: int) -> None:
    target = str(action.get("url") or "")

    if not _scheme_ok(target):
        raise ValueError("Переход разрешён только на http/https.")

    page.goto(target, wait_until="domcontentloaded", timeout=timeout)
    page.wait_for_timeout(SETTLE_MS)


def _act_back(page, action: dict, timeout: int) -> None:
    page.go_back(wait_until="domcontentloaded", timeout=timeout)
    page.wait_for_timeout(500)


def _act_click(page, action: dict, timeout: int) -> None:
    page.click(str(action.get("selector") or ""))


def _act_fill(page, action: dict, timeout: int) -> None:
    page.fill(
        str(action.get("selector") or ""),
        str(action.get("text") or ""),
    )


def _act_press(page, action: dict, timeout: int) -> None:
    page.press(
        str(action.get("selector") or ""),
        str(action.get("key") or "Enter"),
    )


def _act_hover(page, action: dict, timeout: int) -> None:
    page.hover(str(action.get("selector") or ""))


def _act_select(page, action: dict, timeout: int) -> None:
    page.select_option(
        str(action.get("selector") or ""),
        str(action.get("value") or ""),
    )


def _act_scroll(page, action: dict, timeout: int) -> None:
    pixels = int(action.get("pixels") or 800)
    page.mouse.wheel(0, max(-10_000, min(10_000, pixels)))


def _act_wait(page, action: dict, timeout: int) -> None:
    page.wait_for_timeout(
        max(0, min(10_000, int(action.get("ms") or 500)))
    )


ACTIONS = {
    "goto": _act_goto,
    "back": _act_back,
    "click": _act_click,
    "fill": _act_fill,
    "press": _act_press,
    "hover": _act_hover,
    "select": _act_select,
    "scroll": _act_scroll,
    "wait": _act_wait,
}


def _run_actions(page, actions: list, timeout: int) -> None:
    """Выполняет переходы и действия по очереди."""

    for action in actions[:12]:
        if not isinstance(action, dict):
            continue

        handler = ACTIONS.get(
            str(action.get("type") or "").strip().lower()
        )

        if handler is not None:
            handler(page, action, timeout)


def render(request: dict) -> dict:
    """Открывает страницу, выполняет действия и возвращает текст."""

    from playwright.sync_api import sync_playwright

    url = str(request.get("url") or "")
    timeout = int(request.get("timeout_ms") or 60_000)
    wait = str(request.get("wait") or "").strip()
    actions = request.get("actions")
    shot_path = str(request.get("shot_path") or "")

    if not _scheme_ok(url):
        return {"ok": False, "error": "Разрешены только http и https."}

    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage"],
        )

        try:
            page = browser.new_page(accept_downloads=False)
            page.set_default_timeout(timeout)
            page.route("**/*", _guard)
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout,
            )

            if wait:
                page.wait_for_selector(wait, timeout=timeout)
            else:
                page.wait_for_timeout(
                    int(request.get("settle_ms") or SETTLE_MS)
                )

            if isinstance(actions, list) and actions:
                _run_actions(page, actions, timeout)
                page.wait_for_timeout(500)

            if shot_path:
                from pathlib import Path

                Path(shot_path).parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                page.screenshot(
                    path=shot_path,
                    full_page=bool(request.get("full_page")),
                )

            title = page.title()
            text, truncated = _clip(page.inner_text("body"))
            final_url = page.url

            return {
                "ok": True,
                "url": final_url,
                "title": title,
                "text": text,
                "truncated": truncated,
                "shot": shot_path,
            }
        finally:
            browser.close()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    try:
        result = render(_request())
    except Exception as error:  # noqa: BLE001 — ошибку увидит агент
        result = {
            "ok": False,
            "error": f"{type(error).__name__}: {error}",
        }

    print(json.dumps(result, ensure_ascii=False))

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
