# Giperion/app/skills/search/bing.py                              v001
# Разбор RSS и HTML-выдачи Bing.
# Последнее изменение: выделено из web_search.

import base64
import html
import re
import urllib.parse
import xml.etree.ElementTree as ElementTree

from app.skills.search.errors import WebSearchError
from app.skills.search.html_tools import clean_html

_BLOCK_RE = re.compile(
    r'<li class="b_algo".*?</li>',
    re.S,
)
_TITLE_RE = re.compile(
    r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.S,
)
_SNIPPET_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
_SOURCE_RE = re.compile(
    r'<a[^>]*class="tilk"[^>]*aria-label="([^"]+)"',
    re.S,
)
_CITE_RE = re.compile(r"<cite[^>]*>(.*?)</cite>", re.S)


def _decode_result_url(href: str) -> str:
    """Достаёт настоящий адрес из редиректа Bing."""

    href = html.unescape(href)

    match = re.search(
        r"[?&](?:amp;)?u=a1([^&\"]+)",
        href,
    )

    if match:
        value = match.group(1) + "=" * (-len(match.group(1)) % 4)

        try:
            decoded = base64.urlsafe_b64decode(value).decode(
                "utf-8"
            )

            if decoded.startswith(("http://", "https://")):
                return decoded
        except (ValueError, UnicodeDecodeError):
            pass

    if href.startswith("//"):
        return "https:" + href

    if href.startswith(("http://", "https://")):
        return href

    return ""


def _source_from_url(url: str) -> str:
    """Короткое имя источника без www."""

    try:
        host = urllib.parse.urlsplit(url).netloc
    except ValueError:
        return ""

    return host[4:] if host.startswith("www.") else host


def parse_rss_results(
    document: str,
    limit: int = 4,
) -> list[dict]:
    """Разбирает RSS-выдачу Bing."""

    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise WebSearchError(
            "поисковик вернул некорректный RSS"
        ) from error

    results = []

    for item in root.findall("./channel/item"):
        title = clean_html(item.findtext("title", ""))
        snippet = clean_html(
            item.findtext("description", "")
        )
        url = (item.findtext("link", "") or "").strip()

        if not title or not url:
            continue

        results.append(
            {
                "title": title,
                "snippet": snippet,
                "source": _source_from_url(url),
                "url": url,
            }
        )

        if len(results) >= max(1, limit):
            break

    return results


def parse_bing_results(
    document: str,
    limit: int = 4,
) -> list[dict]:
    """Разбирает выдачу Bing на заголовки, описания и источники."""

    results = []

    for block in _BLOCK_RE.findall(document):
        title_match = _TITLE_RE.search(block)

        if title_match is None:
            continue

        title = clean_html(title_match.group(2))

        if not title:
            continue

        snippet_match = _SNIPPET_RE.search(block)
        snippet = (
            clean_html(snippet_match.group(1))
            if snippet_match
            else ""
        )

        url = _decode_result_url(title_match.group(1))

        source_match = _SOURCE_RE.search(block)

        if source_match:
            source = clean_html(source_match.group(1))
        else:
            cite_match = _CITE_RE.search(block)
            source = (
                clean_html(cite_match.group(1))
                if cite_match
                else _source_from_url(url)
            )

        results.append(
            {
                "title": title,
                "snippet": snippet,
                "source": source,
                "url": url,
            }
        )

        if len(results) >= max(1, limit):
            break

    return results
