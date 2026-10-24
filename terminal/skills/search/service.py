# Giperion/app/skills/search/service.py                           v001
# Оркестрация поиска: Bing RSS/HTML и запасная Википедия.
# Последнее изменение: выделено из web_search.

import urllib.parse
import urllib.request

from terminal.skills.search.bing import (
    parse_bing_results,
    parse_rss_results,
)
from terminal.skills.search.constants import (
    BING_RSS_URL,
    BING_URL,
    SEARCH_TIMEOUT,
    USER_AGENT,
)
from terminal.skills.search.errors import WebSearchError
from terminal.skills.search.wikipedia import search_wikipedia


def search_web(query: str, limit: int = 4) -> list[dict]:
    """Ищет в интернете и возвращает несколько результатов."""

    clean_query = " ".join(query.split())

    if not clean_query:
        raise WebSearchError("пустой поисковый запрос")

    encoded_query = urllib.parse.quote_plus(clean_query)
    last_error = None

    providers = (
        (BING_RSS_URL + encoded_query, parse_rss_results),
        (BING_URL + encoded_query, parse_bing_results),
    )

    # Сначала пробуем компактный RSS: его проще разобрать. Если Bing
    # показал готовый виджет без ссылок, переходим к обычной странице.
    for url, parser in providers:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=SEARCH_TIMEOUT,
            ) as response:
                document = response.read().decode(
                    "utf-8",
                    "replace",
                )
        except Exception as error:
            last_error = error
            continue

        try:
            results = parser(document, limit)
        except WebSearchError:
            continue

        if results:
            return results

    # Если поисковик показал только готовый ответ без ссылок,
    # пробуем энциклопедию — для вопросов «что такое …».
    wiki_results = search_wikipedia(
        clean_query,
        min(limit, 3),
    )

    if wiki_results:
        return wiki_results

    if last_error is not None:
        raise WebSearchError(
            "сеть недоступна "
            f"({last_error.__class__.__name__})"
        ) from last_error

    raise WebSearchError(
        "поисковик не вернул подходящих страниц"
    )
