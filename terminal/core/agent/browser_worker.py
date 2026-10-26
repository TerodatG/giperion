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
            args=[
                "--disable-dev-shm-usage",
                "--disable-crash-reporter",
                "--disable-breakpad",
            ],
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


def _guard_ws(route) -> None:
    """Не пускает WebSocket на локальные хосты."""

    from terminal.core.agent import web

    try:
        host = urllib.parse.urlsplit(route.url).hostname or ""
    except Exception:  # noqa: BLE001
        route.close()
        return

    if not web.is_public_host(host):
        route.close()
        return

    route.connect_to_server()


def _new_page(runtime):
    """Браузер, контекст и страница с защитой сети."""

    browser = runtime.chromium.launch(
        headless=True,
        args=[
            "--disable-dev-shm-usage",
            "--disable-crash-reporter",
            "--disable-breakpad",
        ],
    )
    context = browser.new_context(accept_downloads=False)
    context.route("**/*", _guard)
    route_ws = getattr(context, "route_web_socket", None)

    if callable(route_ws):
        try:
            route_ws("**/*", _guard_ws)
        except Exception:  # noqa: BLE001 — старая версия Playwright
            pass

    page = context.new_page()
    page.set_default_timeout(60_000)

    return browser, context, page


def _page_data(page) -> dict:
    """Текущий URL, заголовок и текст."""

    text, truncated = _clip(page.inner_text("body"))

    return {
        "url": page.url,
        "title": page.title(),
        "text": text,
        "truncated": truncated,
    }


def _take_shot(page, request: dict) -> str:
    """Скриншот, если запрошен."""

    shot_path = str(request.get("shot_path") or "")

    if not shot_path:
        return ""

    from pathlib import Path

    Path(shot_path).parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=shot_path,
        full_page=bool(request.get("full_page")),
    )

    return shot_path


def _open_page(page, request: dict, timeout: int) -> dict:
    """Переход, ожидание, действия и скриншот."""

    wait = str(request.get("wait") or "").strip()
    page.goto(
        str(request.get("url") or ""),
        wait_until="domcontentloaded",
        timeout=timeout,
    )

    if wait:
        page.wait_for_selector(wait, timeout=timeout)
    else:
        page.wait_for_timeout(
            int(request.get("settle_ms") or SETTLE_MS)
        )

    actions = request.get("actions")

    if isinstance(actions, list) and actions:
        _run_actions(page, actions, timeout)
        page.wait_for_timeout(500)

    data = _page_data(page)
    data["shot"] = _take_shot(page, request)

    return data


def _act_page(page, request: dict, timeout: int) -> dict:
    """Действия на текущей странице без перехода."""

    actions = request.get("actions")

    if isinstance(actions, list) and actions:
        _run_actions(page, actions, timeout)
        page.wait_for_timeout(500)

    data = _page_data(page)
    data["shot"] = _take_shot(page, request)

    return data


def _close_state(state: dict) -> None:
    """Закрывает браузер сессии."""

    browser = state.get("browser")

    if browser is not None:
        try:
            browser.close()
        except Exception:  # noqa: BLE001
            pass

    state["browser"] = None
    state["page"] = None


def _serve_command(state: dict, runtime, request: dict) -> dict:
    """Один запрос в режиме --serve."""

    command = str(request.get("cmd") or "open").lower()

    if command == "close":
        _close_state(state)

        return {}

    if command == "ping":
        return {"pong": True}

    if state.get("page") is None:
        browser, _context, page = _new_page(runtime)
        state["browser"] = browser
        state["page"] = page

    page = state["page"]
    timeout = int(request.get("timeout_ms") or 60_000)

    if command == "back":
        page.go_back(wait_until="domcontentloaded", timeout=timeout)
        page.wait_for_timeout(500)

        return _page_data(page)

    if command in ("act", "read"):
        if command == "read":
            data = _page_data(page)
            data["shot"] = _take_shot(page, request)

            return data

        return _act_page(page, request, timeout)

    return _open_page(page, request, timeout)


def serve() -> None:
    """Долгоживущий режим: JSON-строки stdin → JSON-строки stdout."""

    import threading
    import time

    from playwright.sync_api import sync_playwright

    runtime = sync_playwright().start()
    state: dict = {"browser": None, "page": None}
    last = {"at": time.monotonic()}
    stop = threading.Event()

    def idle_watch() -> None:
        while not stop.wait(30):
            if not state.get("page"):
                continue

            if time.monotonic() - last["at"] > 300:
                _close_state(state)

    threading.Thread(target=idle_watch, daemon=True).start()

    try:
        for line in sys.stdin:
            text = line.strip()

            if not text:
                continue

            last["at"] = time.monotonic()

            try:
                request = json.loads(text)
            except json.JSONDecodeError:
                continue

            request_id = request.get("id")

            try:
                data = _serve_command(state, runtime, request)
                answer = {"id": request_id, "ok": True, **data}
            except Exception as error:  # noqa: BLE001
                answer = {
                    "id": request_id,
                    "ok": False,
                    "error": f"{type(error).__name__}: {error}",
                }

            print(
                json.dumps(answer, ensure_ascii=False),
                flush=True,
            )

            if request.get("cmd") == "close":
                break
    finally:
        stop.set()
        _close_state(state)
        runtime.stop()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")

    if "--serve" in sys.argv[1:]:
        serve()

        return 0

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
