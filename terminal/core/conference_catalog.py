# Giperion/app/core/conference_catalog.py                          v002
# Режимы сената нескольких моделей и выбранный режим.
# Последнее изменение: короткие подписи для вертикального каталога.

from config import DATA_DIR
from shared.storage.json_store import read_json_object, update_json
from terminal.core.model_catalog import (
    get_model,
)
from terminal.core.model_settings import (
    load_conference_ids,
)

CONFERENCE_SETTINGS_FILE = DATA_DIR / "conference_settings.json"

CONFERENCE_MODES = (
    {
        "id": "council",
        "name": "Параллельный совет",
        "list_hint": "параллельные ответы",
        "summary": (
            "Все участники получают одну и ту же реплику и отвечают "
            "независимо друг от друга."
        ),
        "details": (
            "В следующем сообщении каждая модель видит полный транскрипт, "
            "включая ответы других участников. Самый быстрый и простой "
            "режим для знакомства с сенатом."
        ),
    },
    {
        "id": "debate",
        "name": "Дебаты",
        "list_hint": "по очереди",
        "summary": (
            "Модели отвечают по очереди и видят ответы предыдущих "
            "участников этого раунда."
        ),
        "details": (
            "Позволяет моделям спорить и уточнять позиции друг друга. "
            "Планируются один-два раунда; каждый раунд занимает больше "
            "времени, чем параллельный совет."
        ),
    },
    {
        "id": "moderator",
        "name": "Модератор",
        "list_hint": "один итоговый ответ",
        "summary": (
            "Участники отвечают параллельно, а затем выбранная модель "
            "сводит их ответы в одну итоговую реплику."
        ),
        "details": (
            "Даёт один чистый ответ, но требует отдельной модели-"
            "модератора. Пока режим подготовлен без выбора модератора."
        ),
    },
)


def get_mode(mode_id: str) -> dict | None:
    """Возвращает описание режима сената."""

    return next(
        (
            mode
            for mode in CONFERENCE_MODES
            if mode["id"] == mode_id
        ),
        None,
    )


def get_selected_mode_id() -> str:
    """Возвращает сохранённый режим или первый доступный."""

    document = read_json_object(CONFERENCE_SETTINGS_FILE)
    mode_id = document.get("mode_id")

    if isinstance(mode_id, str) and get_mode(mode_id):
        return mode_id

    return CONFERENCE_MODES[0]["id"]


def set_selected_mode_id(mode_id: str) -> bool:
    """Запоминает выбранный режим сената."""

    if get_mode(mode_id) is None:
        return False

    def mutate(document: dict) -> dict:
        document["mode_id"] = mode_id

        return document

    update_json(
        CONFERENCE_SETTINGS_FILE,
        mutate,
        default={},
    )

    return True


def get_conference_members() -> list[dict]:
    """Возвращает отмеченных участников сената."""

    return [
        model
        for model_id in load_conference_ids()
        if (model := get_model(model_id)) is not None
    ]
