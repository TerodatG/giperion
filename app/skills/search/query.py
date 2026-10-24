# Giperion/app/skills/search/query.py                             v001
# Распознавание команды поиска и извлечение запроса.
# Последнее изменение: выделено из web_search.

from app.skills.search.constants import SEARCH_COMMANDS


def extract_search_query(message: str) -> str | None:
    """Возвращает запрос, если сообщение просит поискать в интернете."""

    text = " ".join(message.strip().split())

    if not text:
        return None

    lowered = text.lower()

    for command in SEARCH_COMMANDS:
        index = lowered.find(command)

        if index < 0:
            continue

        query = text[index + len(command):].strip(
            " \t\n.,:;!?—–-"
        )

        if query.lower().startswith("о "):
            query = query[2:].strip()

        return query

    return None
