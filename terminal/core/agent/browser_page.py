# Giperion/terminal/core/agent/browser_page.py                        v001
# Текст, заголовок и скриншот страницы.
# Последнее изменение: вынесено из browser_worker.

from pathlib import Path

MAX_TEXT = 12_000


def clip(text: str) -> tuple[str, bool]:
    """Обрезает текст страницы до лимита."""

    value = str(text or "")
    truncated = len(value) > MAX_TEXT

    if truncated:
        return value[: MAX_TEXT - 1] + "…", True

    return value, False


def page_data(page) -> dict:
    """Текущий URL, заголовок и текст."""

    text, truncated = clip(page.inner_text("body"))

    return {
        "url": page.url,
        "title": page.title(),
        "text": text,
        "truncated": truncated,
    }


def take_shot(page, request: dict) -> str:
    """Скриншот, если запрошен."""

    shot_path = str(request.get("shot_path") or "")

    if not shot_path:
        return ""

    Path(shot_path).parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=shot_path,
        full_page=bool(request.get("full_page")),
    )

    return shot_path
