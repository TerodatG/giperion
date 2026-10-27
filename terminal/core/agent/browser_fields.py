# Giperion/terminal/core/agent/browser_fields.py                      v001
# Поля действий браузера: ввод, ожидания, прокрутка и вкладки.
# Последнее изменение: вынесено из browser_js.

import urllib.parse


def _simple_values(action: dict, item: dict, kind: str) -> bool:
    """Поля ввода, прокрутки и паузы."""

    if kind == "fill":
        action["text"] = str(item.get("text") or "")[:2000]
    elif kind == "press":
        action["key"] = str(item.get("key") or "Enter")[:30]
    elif kind == "select":
        action["value"] = str(item.get("value") or "")[:200]
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

    return True


def _target_values(action: dict, item: dict, kind: str) -> bool:
    """Поля ожиданий и вкладок."""

    if kind == "wait_text":
        text = str(item.get("text") or "").strip()[:200]

        if not text:
            return False

        action["text"] = text
    elif kind == "wait_url":
        target = str(item.get("url") or "").strip()[:2048]

        if not target:
            return False

        action["url"] = target
    elif kind == "new_tab":
        target = str(item.get("url") or "").strip()[:2048]

        if target:
            scheme = urllib.parse.urlsplit(target).scheme

            if scheme not in ("http", "https"):
                return False

            action["url"] = target
    elif kind == "switch_tab":
        action["index"] = max(
            0,
            min(20, int(item.get("index") or 0)),
        )

    return True


def extra_values(action: dict, item: dict, kind: str) -> bool:
    """Дополнительные поля действия; False — пропустить."""

    return _simple_values(action, item, kind) and _target_values(
        action,
        item,
        kind,
    )
