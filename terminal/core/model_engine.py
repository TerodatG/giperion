# Giperion/app/core/model_engine.py                                v006
# Ответ активной модели и учёт обращений к ней.
# Последнее изменение: внешняя модель больше не представляется в ответе.

from dataclasses import dataclass

from terminal.core.chatbot import get_response
from terminal.core.model_catalog import (
    DEFAULT_MODEL_ID,
    get_model,
)
from terminal.core.model_errors import (
    describe_model_error as _describe_model_error,
)
from terminal.core.model_settings import (
    get_current_model_id,
)
from terminal.core.model_stats import (
    record_model_request,
)
from terminal.core.opencode_client import OpenCodeError, ask_model

# Просьба к внешней модели говорить как собеседник, а не как сборщик кода.
CHAT_PREFIX = (
    "Ты — ИИ-собеседник в оконном приложении «Гиперион». "
    "Отвечай по-русски, коротко и по делу, без упоминания инструментов, "
    "файлов и служебных команд. Не представляйся, не называй своё имя "
    "или название модели и не начинай ответ словами «Я — …», если "
    "пользователь прямо не спросил, кто ты."
)

CONTEXT_HINT = (
    "Ниже — история этого чата без системных сообщений. "
    "Учитывай её и продолжай разговор по смыслу."
)

# Признаки исчерпанного лимита живут в app/core/model_errors.py.


@dataclass
class ModelResponse:
    """Ответ модели вместе со служебными признаками.

    Распаковывается как пара (текст, сохранять_в_историю), поэтому старые
    вызовы продолжают работать без изменений.
    """

    text: str
    save_to_history: bool = False
    error: bool = False
    reason: str = ""

    def __iter__(self):
        """Позволяет писать `answer, save = response`."""

        yield self.text
        yield self.save_to_history


def describe_model_error(model_name: str, error: object) -> str:
    """Совместимый реэкспорт: ошибки описаны в model_errors."""

    return _describe_model_error(model_name, error)


def build_external_prompt(
    model_name: str,
    text: str,
    context: str = "",
) -> str:
    """Собирает запрос к внешней модели с историей текущего чата."""

    parts = [CHAT_PREFIX.format(name=model_name)]

    clean_context = context.strip()

    if clean_context:
        parts.append(CONTEXT_HINT)
        parts.append(clean_context)

    parts.append(f"Пользователь: {text}")

    return "\n\n".join(parts)


def get_model_response(
    text: str,
    context: str = "",
) -> ModelResponse:
    """Отвечает от имени активной модели.

    Собственное ядро работает локально и считает токены по словам.
    Внешняя модель отвечает через локальный сервис OpenCode и получает
    выжимку текущего чата; расход токенов берётся из её ответа.

    Ошибка внешней модели возвращается с признаком `error=True`: окно
    показывает её в поле системных сообщений и не пишет в историю.
    """

    model_id = get_current_model_id()
    model = get_model(model_id)

    if model_id == DEFAULT_MODEL_ID or model is None:
        record_model_request(model_id, len(text.split()))

        result = get_response(text)
        answer, save_to_history = result
        external_error = str(
            getattr(result, "external_error", "")
        )

        if external_error:
            # Локальное ядро тоже может звать внешнюю модель-помощника.
            return ModelResponse(
                answer,
                False,
                True,
                external_error,
            )

        return ModelResponse(answer, save_to_history)

    if not model["available"] or not model["model_id"]:
        record_model_request(model_id, len(text.split()))

        return ModelResponse(
            f"Модель «{model['name']}» выбрана, но канал связи с ней "
            "ещё не настроен. Выбери Гипериона в окне «Модель» — "
            "он ответит прямо сейчас.",
            False,
            True,
            "канал связи не настроен",
        )

    try:
        answer, usage = ask_model(
            model["model_id"],
            build_external_prompt(
                model["name"],
                text,
                context,
            ),
            provider_id=model["provider_id"] or "opencode",
            title=f"Гиперион · {model['name']}",
        )
    except OpenCodeError as error:
        record_model_request(model_id, len(text.split()))

        return ModelResponse(
            describe_model_error(model["name"], error),
            False,
            True,
            str(error),
        )

    record_model_request(model_id, usage["total"])

    return ModelResponse(answer, True)
