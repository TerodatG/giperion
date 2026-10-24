# Giperion/app/skills/search/html_tools.py                        v001
# Очистка HTML-фрагментов поисковой выдачи.

import html
import re


def clean_html(value: str) -> str:
    """Убирает теги и лишние пробелы из куска HTML."""

    text = re.sub(r"<[^>]+>", "", value)
    text = html.unescape(text)
    text = text.replace("\u200c", " ")

    return " ".join(text.split()).strip()
