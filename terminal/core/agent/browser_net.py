# Giperion/terminal/core/agent/browser_net.py                         v001
# Сетевая защита браузера: пиннинг хоста через host-resolver-rules.
# Последнее изменение: вынесено из browser_worker.

import urllib.parse


def resolver_args(url: str) -> list[str]:
    """Chromium: прибить хост к проверенному IP."""

    from terminal.core.agent import web

    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return []

    addresses = web.resolve_public(host)

    if not addresses:
        return []

    return [f"--host-resolver-rules=MAP {host} {addresses[0]}"]
