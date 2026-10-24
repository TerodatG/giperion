# Giperion/app/core/character_handler.py                          v002
# Обработка команд просмотра параметров ИИ-ядра Giperion.
# Последнее изменение: добавлены прогресс-бар развития и разбивка опыта.

from app.core.character_service import get_characteristics
from app.language.vocabulary.phrases import SHOW_CHARACTERISTICS_COMMANDS


def make_progress_bar(percent: int, width: int = 20) -> str:
    """Рисует текстовый прогресс-бар развития."""

    filled = round(width * percent / 100)

    return (
        "█" * filled
        + "░" * (width - filled)
    )


def get_characteristics_response() -> str:
    """Возвращает текст с параметрами ИИ-ядра."""

    characteristics = get_characteristics()

    progress_bar = make_progress_bar(
        int(characteristics["level_percent"])
    )

    lines = [
        "Параметры ИИ-ядра:",
        f"Идентификатор: {characteristics['identifier']}",
        f"Тип: {characteristics['system_type']}",
        f"Версия ядра: {characteristics['core_version']}",
        f"Уровень: {characteristics['level']}",
        f"Опыт: {characteristics['experience']}",
        f"Рост: [{progress_bar}] "
        f"{characteristics['level_percent']}% "
        f"(до след. уровня: {characteristics['level_remaining']})",
        f"Активные навыки: {characteristics['skills_count']}",
        f"Записей памяти: {characteristics['memory_records_count']}",
        f"Непонятых фраз: {characteristics['unknown_messages_count']}",
        f"Статус ядра: {characteristics['status']}",
    ]

    return "\n".join(lines)


def get_characteristics_command_response(message: str) -> str | None:
    """Возвращает параметры ядра по соответствующей команде."""

    if any(command in message for command in SHOW_CHARACTERISTICS_COMMANDS):
        return get_characteristics_response()

    return None