# Giperion/app/core/helper_model.py                                 v002
# Помощь внешней модели, когда локальное ядро не уверено в ответе.
# Последнее изменение: компаньоны и выбор по репутации и навыкам.

from terminal.core.model_catalog import (
    DEFAULT_MODEL_ID,
    load_models,
)
from terminal.core.model_settings import (
    load_companion_ids,
)
from terminal.core.model_stats import (
    get_reputation,
    record_model_request,
)
from terminal.core.opencode_client import ask_model

HELPER_PROMPT = (
    "Ты помогаешь локальному ядру «Гиперион» ответить на реплику "
    "пользователя. Ответь по-русски, коротко и по делу. Не "
    "представляйся и не упоминай, что ты внешняя модель.\n\n"
    "Реплика пользователя:\n{message}"
)


def get_skill_score(model: dict) -> int:
    """Суммарный навык модели по всем сильным сторонам."""

    strengths = model.get("strengths") or {}

    return sum(
        value
        for value in strengths.values()
        if isinstance(value, int)
    )


def get_model_rank(model: dict) -> tuple:
    """Ключ выбора помощника: репутация, затем навык, затем имя.

    Репутация — это число обращений. Если обращения равны, побеждает
    модель с большей суммой навыков; имя нужно только для стабильного
    результата при полном равенстве.
    """

    reputation = get_reputation(model["id"])

    return (
        reputation["requests"],
        get_skill_score(model),
        model["name"],
    )


def get_helper_model() -> dict | None:
    """Возвращает внешнюю модель, доступную для помощи.

    Если в карточках отмечены компаньоны, выбор идёт только среди них.
    Когда компаньонов нет (или ни один не подключён), помощь получает
    лучшая из всех доступных внешних моделей по репутации и навыкам.
    """

    external = [
        model
        for model in load_models()
        if model["id"] != DEFAULT_MODEL_ID
        and model["available"]
        and model["model_id"]
    ]

    if not external:
        return None

    companion_ids = set(load_companion_ids())
    companions = [
        model
        for model in external
        if model["id"] in companion_ids
    ]

    candidates = companions or external

    return max(candidates, key=get_model_rank)


def ask_helper(message: str) -> tuple[str, str] | None:
    """Спрашивает внешнюю модель и возвращает ответ и её имя.

    None означает, что подходящей внешней модели нет.
    """

    model = get_helper_model()

    if model is None:
        return None

    answer, usage = ask_model(
        model["model_id"],
        HELPER_PROMPT.format(message=message.strip()),
        provider_id=model["provider_id"],
        title="Помощь моделей",
    )

    record_model_request(
        model["id"],
        usage.get("total", 0),
    )

    return answer.strip(), model["name"]
