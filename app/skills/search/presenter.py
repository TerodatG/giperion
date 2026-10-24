# Giperion/app/skills/search/presenter.py                         v001
# Оформление ответа со ссылками на найденные страницы.
# Последнее изменение: выделено из web_search.

from app.skills.search.constants import INTERNET_ANSWER_PREFIX


def format_search_results(
    query: str,
    results: list[dict],
) -> str:
    """Собирает короткий ответ со ссылками на источники."""

    lines = [
        f"{INTERNET_ANSWER_PREFIX} по запросу «{query}»:",
    ]

    for index, result in enumerate(results, start=1):
        lines.append(
            f"{index}. {result['title']}"
        )

        if result["snippet"]:
            lines.append(f"   {result['snippet']}")

        source = result.get("source") or "источник не указан"
        lines.append(f"   Источник: {source}")

    lines.append(
        "Это краткая выжимка. Полный текст страницы я не "
        "пересказываю — могу поискать точнее."
    )

    return "\n".join(lines)
