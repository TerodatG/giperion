# Giperion/app/skills/search/__init__.py                          v002
# Поиск в интернете: запрос, источники, сервис и оформление ответа.

from app.skills.search.bing import (
    parse_bing_results,
    parse_rss_results,
)
from app.skills.search.constants import INTERNET_ANSWER_PREFIX
from app.skills.search.errors import WebSearchError
from app.skills.search.presenter import format_search_results
from app.skills.search.query import extract_search_query
from app.skills.search.service import search_web

__all__ = [
    "INTERNET_ANSWER_PREFIX",
    "WebSearchError",
    "extract_search_query",
    "format_search_results",
    "parse_bing_results",
    "parse_rss_results",
    "search_web",
]
