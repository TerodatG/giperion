# Giperion/tests/test_web_search.py                                  v001
# Проверки поиска в интернете без обращения к сети.
# Последнее изменение: извлечение запроса, RSS, HTML и формат ответа.

import base64

from terminal.skills.web_search import (
    extract_search_query,
    format_search_results,
    parse_bing_results,
    parse_rss_results,
)


def test_extract_search_query() -> None:
    """Команда поиска отделяет запрос от служебных слов."""

    assert (
        extract_search_query(
            "Найди в интернете курс доллара"
        )
        == "курс доллара"
    )
    assert extract_search_query("погугли Python") == "Python"
    assert extract_search_query("привет") is None
    assert extract_search_query("найди в интернете") == ""


def test_parse_rss_results() -> None:
    """RSS-выдача превращается в заголовки, описания и источники."""

    document = """<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0"><channel>
<item>
  <title>Пример статьи</title>
  <link>https://example.org/article</link>
  <description>Короткое &lt;b&gt;описание&lt;/b&gt;.</description>
</item>
</channel></rss>"""

    results = parse_rss_results(document)

    assert len(results) == 1
    assert results[0]["title"] == "Пример статьи"
    assert results[0]["snippet"] == "Короткое описание."
    assert results[0]["source"] == "example.org"
    assert results[0]["url"] == "https://example.org/article"


def test_parse_bing_html_and_redirect() -> None:
    """HTML-выдача Bing и редирект дают настоящий адрес."""

    target = base64.urlsafe_b64encode(
        b"https://example.org/page"
    ).decode("ascii").rstrip("=")

    document = (
        '<li class="b_algo">'
        '<h2><a href="https://www.bing.com/ck/a?u=a1'
        f'{target}">Заголовок</a></h2>'
        '<p>Описание результата</p>'
        "</li>"
    )

    results = parse_bing_results(document)

    assert len(results) == 1
    assert results[0]["title"] == "Заголовок"
    assert results[0]["snippet"] == "Описание результата"
    assert results[0]["url"] == "https://example.org/page"
    assert results[0]["source"] == "example.org"


def test_format_search_results() -> None:
    """Ответ показывает запрос, заголовки и источники."""

    answer = format_search_results(
        "курс доллара",
        [
            {
                "title": "Курс на сегодня",
                "snippet": "82 рубля.",
                "source": "example.org",
                "url": "https://example.org",
            }
        ],
    )

    assert "курс доллара" in answer
    assert "Курс на сегодня" in answer
    assert "example.org" in answer
