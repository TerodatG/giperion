# Giperion/terminal/core/agent/browser_tabs.py                        v001
# Действия с вкладками: новая, переключение и закрытие.
# Последнее изменение: вынесено из browser_worker.

import urllib.parse


def _scheme_ok(url: str) -> bool:
    try:
        return urllib.parse.urlsplit(url).scheme in ("http", "https")
    except ValueError:
        return False


def apply(current, kind: str, action: dict, timeout: int, settle_ms: int):
    """Выполняет действие вкладки; None — это не действие вкладки."""

    if kind == "new_tab":
        page = current.context.new_page()
        page.set_default_timeout(timeout)
        target = str(action.get("url") or "")

        if target:
            if not _scheme_ok(target):
                raise ValueError("Переход разрешён только на http/https.")

            page.goto(
                target,
                wait_until="domcontentloaded",
                timeout=timeout,
            )
            page.wait_for_timeout(settle_ms)

        return page

    if kind == "switch_tab":
        pages = current.context.pages

        if not pages:
            return current

        index = int(action.get("index") or 0)

        return pages[max(0, min(len(pages) - 1, index))]

    if kind == "close_tab":
        context = current.context
        pages = list(context.pages)

        if len(pages) > 1:
            current.close()

            return context.pages[0]

        return current

    return None
