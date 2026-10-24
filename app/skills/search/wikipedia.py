# Giperion/app/skills/search/wikipedia.py                         v001
# Запасной поиск по русской Википедии.
# Последнее изменение: выделено из web_search.

import json
import urllib.parse
import urllib.request

from app.skills.search.html_tools import clean_html
from app.skills.search.constants import (
    LIVE_QUERY_WORDS,
    SEARCH_TIMEOUT,
    WIKIPEDIA_API,
)


def search_wikipedia(
    query: str,
    limit: int = 3,
) -> list[dict]:
    """Ищет статьи в русской Википедии как запасной источник."""

    lowered = query.lower()

    if any(word in lowered for word in LIVE_QUERY_WORDS):
        return []

    wiki_query = query

    for prefix in (
        "что такое ",
        "что значит ",
        "кто такой ",
        "кто такая ",
        "расскажи про ",
        "расскажи о ",
    ):
        if lowered.startswith(prefix):
            wiki_query = query[len(prefix):].strip()
            break

    request = urllib.request.Request(
        WIKIPEDIA_API + urllib.parse.quote_plus(wiki_query),
        headers={
            "User-Agent": (
                "Giperion/0.1 (local educational assistant)"
            )
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=SEARCH_TIMEOUT,
        ) as response:
            document = json.loads(
                response.read().decode("utf-8")
            )
    except Exception:
        return []

    results = []

    for item in (
        document.get("query", {}).get("search", [])
    ):
        title = str(item.get("title", "")).strip()
        page_id = item.get("pageid")

        if not title or not page_id:
            continue

        results.append(
            {
                "title": title,
                "snippet": clean_html(
                    str(item.get("snippet", ""))
                ),
                "source": "ru.wikipedia.org",
                "url": (
                    "https://ru.wikipedia.org/?curid="
                    f"{page_id}"
                ),
            }
        )

        if len(results) >= max(1, limit):
            break

    return results
