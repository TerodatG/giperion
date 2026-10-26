# Giperion/terminal/core/agent/web.py                                  v001
# Чтение веб-страниц агентом: один GET, текст без тегов, защита от SSRF.
# Последнее изменение: первый вариант — html.parser и подтверждение по домену.

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from terminal.core.agent.protocol import ToolResult

TIMEOUT = 15
MAX_BYTES = 400_000
MAX_TEXT = 12_000
ALLOWED_PORTS = (80, 443)
SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}


class WebError(RuntimeError):
    """Страницу нельзя или не удалось прочитать."""


def _checked_redirect(url: str) -> str:
    """Проверяет адрес редиректа теми же правилами, что и исходный."""

    clean = validate_url(url)

    if not is_public_host(host_of(clean)):
        raise WebError(
            f"Редирект на «{host_of(clean)}» ведёт в локальную "
            "или приватную сеть — запрещено."
        )

    return clean


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Не даёт urlopen уйти редиректом на localhost или в приватную сеть."""

    def redirect_request(
        self,
        request,
        file_pointer,
        code,
        message,
        headers,
        new_url,
    ):
        target = _checked_redirect(
            urllib.parse.urljoin(request.full_url, new_url)
        )

        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            target,
        )


def validate_url(url: str) -> str:
    """Проверяет URL и возвращает нормализованный адрес."""

    text = str(url or "").strip()

    if not text:
        raise WebError("Не передан адрес страницы.")

    if "://" not in text:
        text = "https://" + text

    parsed = urllib.parse.urlsplit(text)

    if parsed.scheme not in ("http", "https"):
        raise WebError("Разрешены только http и https.")

    if not parsed.hostname:
        raise WebError("В адресе нет имени сайта.")

    if parsed.username or parsed.password:
        raise WebError("Адреса с логином и паролем не поддерживаются.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if port not in ALLOWED_PORTS:
        raise WebError("Разрешены только порты 80 и 443.")

    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, "")
    )


def is_public_host(host: str) -> bool:
    """Не ведёт ли имя на localhost или приватную сеть."""

    name = str(host or "").strip()

    if not name:
        return False

    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(name, None)
        }
    except (socket.gaierror, OSError):
        return False

    for address in addresses:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            return False

        if (
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_reserved
            or parsed.is_multicast
            or parsed.is_unspecified
        ):
            return False

    return True


class _TextParser(HTMLParser):
    """Вытаскивает текст, пропуская скрипты и стили."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in SKIP_TAGS:
            self._skip += 1
        elif tag in (
            "p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4",
            "h5", "h6", "article", "section", "pre",
        ):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return

        text = str(data or "").strip()

        if text:
            self.parts.append(text + " ")


def html_to_text(html: str) -> str:
    """Текст страницы без разметки и лишних пустых строк."""

    parser = _TextParser()

    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 — кривой HTML не должен ломать чтение
        pass

    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()


def _http_get(url: str) -> tuple[str, str, bytes]:
    """Один GET с ограничением размера. Отдельно, чтобы подменять в тестах."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Giperion-Terminal/1.0 (agent page reader)",
            "Accept": "text/html,text/plain,application/json;q=0.8",
        },
    )

    try:
        opener = urllib.request.build_opener(
            _SafeRedirectHandler()
        )

        with opener.open(request, timeout=TIMEOUT) as response:
            content_type = response.headers.get("Content-Type", "")
            data = response.read(MAX_BYTES + 1)

            final_url = response.geturl()
    except urllib.error.HTTPError as error:
        raise WebError(f"Сайт ответил кодом {error.code}.") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise WebError(f"Не удалось открыть страницу: {error}") from error

    return final_url, content_type, data


HTTP_GET = _http_get


def host_of(url: str) -> str:
    """Домен страницы для подтверждения."""

    try:
        return urllib.parse.urlsplit(validate_url(url)).hostname or ""
    except WebError:
        return ""


def egress_allowed(host: str) -> bool:
    """Домен входит в общий allowlist (пусто — разрешены все)."""

    from terminal.core.agent import settings

    patterns = settings.egress_domains()

    if not patterns:
        return True

    name = str(host or "").lower().strip(".")

    for pattern in patterns:
        if name == pattern:
            return True

        if pattern.startswith("*.") and name.endswith(
            "." + pattern[2:]
        ):
            return True

    return False


def preview(url: str) -> ToolResult:
    """Предпросмотр: адрес и домен, без запроса в сеть."""

    try:
        clean = validate_url(url)
    except WebError as error:
        return ToolResult(False, str(error))

    host = host_of(clean)

    return ToolResult(
        True,
        f"Открыть страницу\n{clean}\nдомен: {host}",
    )


def fetch(url: str) -> ToolResult:
    """Скачивает страницу и возвращает её текст."""

    try:
        clean = validate_url(url)
    except WebError as error:
        return ToolResult(False, str(error))

    host = host_of(clean)

    if not is_public_host(host):
        return ToolResult(
            False,
            f"Адрес «{host}» ведёт в локальную или приватную сеть — "
            "запрещено.",
        )

    if not egress_allowed(host):
        return ToolResult(
            False,
            f"Домен «{host}» не входит в общий allowlist.",
        )

    try:
        final_url, content_type, data = HTTP_GET(clean)
    except WebError as error:
        return ToolResult(False, str(error))

    final_host = host_of(final_url)

    if not is_public_host(final_host):
        return ToolResult(
            False,
            f"Страница перенаправила на «{final_host}» — локальную "
            "или приватную сеть. Запрос запрещён.",
        )

    if not egress_allowed(final_host):
        return ToolResult(
            False,
            f"Редирект на «{final_host}» вне общего allowlist.",
        )

    if len(data) > MAX_BYTES:
        data = data[:MAX_BYTES]
        cut = True
    else:
        cut = False

    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type or "", re.I)

    if match:
        charset = match.group(1)

    try:
        raw_text = data.decode(charset, "replace")
    except LookupError:
        raw_text = data.decode("utf-8", "replace")

    lower_type = (content_type or "").lower()

    if "html" in lower_type or raw_text.lstrip().startswith("<"):
        text = html_to_text(raw_text)
    else:
        text = raw_text.strip()

    text = text[:MAX_TEXT]

    if len(text) >= MAX_TEXT or cut:
        text += "\n… страница обрезана"

    if not text:
        return ToolResult(
            True,
            f"Страница пустая (текста нет).\nисточник: {final_url}",
        )

    return ToolResult(
        True,
        f"источник: {final_url}\n\n{text}",
    )
