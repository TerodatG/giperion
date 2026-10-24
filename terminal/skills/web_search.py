# Giperion/app/skills/web_search.py                                  v003
# Совместимый фасад поиска в интернете.
# Последнее изменение: реализация разделена на пакет app/skills/search.

from terminal.skills.search import (
    INTERNET_ANSWER_PREFIX,
    WebSearchError,
    extract_search_query,
    format_search_results,
    parse_bing_results,
    parse_rss_results,
    search_web,
)

__all__ = [
    "INTERNET_ANSWER_PREFIX",
    "WebSearchError",
    "extract_search_query",
    "format_search_results",
    "parse_bing_results",
    "parse_rss_results",
    "search_web",
]
