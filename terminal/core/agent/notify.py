# Giperion/terminal/core/agent/notify.py                               v001
# Вебхуки о завершении задач: JSON POST, редакция секретов.
# Последнее изменение: первый вариант — GIPERION_WEBHOOK_URL.

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from terminal.core.agent.redact import redact

TIMEOUT = 10
MAX_RESPONSE = 100_000


def webhook_url() -> str:
    """Адрес вебхука из окружения."""

    return os.environ.get("GIPERION_WEBHOOK_URL", "").strip()


def send(text: str, url: str = "") -> bool:
    """Отправляет короткое уведомление; False — вебхук не задан/сбой."""

    target = str(url or webhook_url()).strip()

    if not target:
        return False

    try:
        parts = urllib.parse.urlsplit(target)
    except ValueError:
        return False

    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False

    payload = json.dumps(
        {"text": redact(str(text or "")[:2_000]).text},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        target,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=TIMEOUT,
        ) as response:
            response.read(MAX_RESPONSE)
    except (OSError, urllib.error.URLError):
        return False

    return True
