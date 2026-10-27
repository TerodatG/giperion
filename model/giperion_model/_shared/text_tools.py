# GiperionModel/giperion_model/_shared/text_tools.py                  v001
# Нормализация и подготовка пользовательского текста Giperion.
# Последнее изменение: файл перемещён в пакет language без изменения логики.

import re


def normalize_message(message: str) -> str:
    """Приводит пользовательское сообщение к удобному виду для анализа."""

    normalized_message = message.lower().strip()
    normalized_message = normalized_message.replace("ё", "е")
    normalized_message = re.sub(
        r"\s+",
        " ",
        normalized_message,
    )

    return normalized_message