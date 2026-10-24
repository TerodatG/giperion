# Giperion/app/core/chat_pipeline.py                               v002
# Этапы ответа Гипериона: от самоописания до честного «не понял».
# Последнее изменение: ошибка модели-помощника помечает ответ ядра.

from dataclasses import dataclass
from typing import Callable

from app.core.character_handler import (
    get_characteristics_command_response,
)
from app.core.helper_model import ask_helper
from app.core.identity_matrix import IDENTITY_MATRIX
from app.core.model_errors import describe_model_error
from app.core.module_state import is_module_enabled
from app.core.opencode_client import OpenCodeError
from app.core.pending_state import (
    set_pending_action,
    set_pending_clarification,
)
from app.help_handler import get_help_response
from app.language.intent_handler import find_close_pattern
from app.language.learning_handler import get_learning_response
from app.language.vocabulary.phrases import (
    CLEAN_LEARNED_MESSAGES_COMMANDS,
    CLEAR_VARIABLES_COMMANDS,
    SHOW_UNKNOWN_MESSAGES_COMMANDS,
    SHOW_VARIABLES_COMMANDS,
)
from app.memory.memory import add_unknown_message
from app.memory.system_handler import (
    get_confirmation_response,
    get_system_command_response,
)
from app.memory.profile_handler import (
    get_name_response,
    get_profile_response,
)
from app.memory.unknown_messages_handler import (
    clean_learned_unknown_messages,
    get_unknown_messages_response,
)
from app.skills.math_handler import (
    clear_variables_response,
    get_math_response,
    get_variables_response,
)
from app.skills.time_handler import get_time_and_date_response
from app.skills.web_search import (
    WebSearchError,
    extract_search_query,
    format_search_results,
    search_web,
)
from giperion.api import generate as generate_answer
from giperion.api import match_intent

# Вопросы, на которые ядро отвечает собственным самоописанием.
IDENTITY_PATTERNS = {
    "кто ты",
    "кто ты такой",
    "кто ты такая",
    "ты кто",
    "ты кто такой",
    "ты кто такая",
    "как тебя зовут",
    "как твое имя",
    "твое имя",
    "представься",
    "представься пожалуйста",
    "расскажи о себе",
    "что ты такое",
    "что ты за программа",
    "что ты за создание",
    "ты бот",
    "ты бот или человек",
    "ты человек",
    "ты робот",
    "ты живой",
    "ты искусственный интеллект",
    "ты ии",
    "ты нейросеть",
    "ты программа",
    "ты машина",
    "ты цифровой помощник",
    "ты виртуальный ассистент",
    "ты разумный",
    "у тебя есть сознание",
    "ты считаешь себя нейросетью",
    "ты считаешь себя искусственным интеллектом",
    "ты относишь себя к нейросетям",
    "ты нейросетевой помощник",
    "кто ты по своей природе",
}

IDENTITY_PREFIXES = ("гиперион", "giperion")


@dataclass(frozen=True)
class ChatContext:
    """Один запрос: нормализованный и исходный текст, режим системы."""

    message: str
    user_message: str
    is_system_mode: bool


StageResult = tuple[str, bool] | None
Stage = Callable[[ChatContext], StageResult]


class CoreResponse(tuple):
    """Ответ ядра, распаковываемый как (текст, сохранять).

    Дополнительный признак `external_error` нужен, когда локальное ядро
    звало внешнюю модель-помощника и получило от неё ошибку. Тогда окно
    показывает её в системном логе, а не как реплику Гипериона.
    """

    def __new__(
        cls,
        text: str,
        save_to_history: bool,
        external_error: str = "",
    ) -> "CoreResponse":
        response = super().__new__(
            cls,
            (text, save_to_history),
        )
        response.external_error = external_error

        return response


def _identity_key(message: str) -> str:
    """Убирает обращение к ядру и знаки, чтобы узнать вопрос о себе."""

    text = message.strip(" \t\r\n?!.,;:—–-")
    lowered = text.lower()

    for prefix in IDENTITY_PREFIXES:
        if lowered == prefix:
            return ""

        if lowered.startswith(prefix):
            tail = text[len(prefix):].lstrip(" \t,;:—–-")

            if tail:
                text = tail.strip(" \t\r\n?!.,;:—–-")

            break

    return text


def identity_stage(context: ChatContext) -> StageResult:
    """Отвечает на вопросы «кто ты» до нейросети и внешних моделей."""

    if _identity_key(context.message) in IDENTITY_PATTERNS:
        return (
            IDENTITY_MATRIX["self_description"],
            True,
        )

    return None


def confirmation_stage(context: ChatContext) -> StageResult:
    """Выполняет или отменяет ожидающее системное действие."""

    answer = get_confirmation_response(context.message)

    if answer:
        return (answer, False)

    return None


def system_command_stage(context: ChatContext) -> StageResult:
    """Обрабатывает системные команды памяти и архивов."""

    answer = get_system_command_response(context.message)

    if answer:
        return (answer, False)

    return None


def characteristics_stage(context: ChatContext) -> StageResult:
    """Показывает параметры ядра по команде."""

    answer = get_characteristics_command_response(context.message)

    if answer:
        return (answer, False)

    return None


def clean_learned_stage(context: ChatContext) -> StageResult:
    """Убирает из накопителя фразы, которые уже есть в намерениях."""

    if any(
        command in context.message
        for command in CLEAN_LEARNED_MESSAGES_COMMANDS
    ):
        return (clean_learned_unknown_messages(), False)

    return None


def clear_variables_stage(context: ChatContext) -> StageResult:
    """Очищает временные переменные калькулятора."""

    if any(
        command in context.message
        for command in CLEAR_VARIABLES_COMMANDS
    ):
        return (clear_variables_response(), False)

    return None


def show_variables_stage(context: ChatContext) -> StageResult:
    """Показывает сохранённые переменные калькулятора."""

    if any(
        command in context.message
        for command in SHOW_VARIABLES_COMMANDS
    ):
        return (get_variables_response(), False)

    return None


def show_unknown_stage(context: ChatContext) -> StageResult:
    """Показывает накопитель непонятых фраз."""

    if any(
        command in context.message
        for command in SHOW_UNKNOWN_MESSAGES_COMMANDS
    ):
        return (get_unknown_messages_response(), False)

    return None


def learning_stage(context: ChatContext) -> StageResult:
    """Обрабатывает команды обучения и управления знаниями."""

    answer = get_learning_response(
        context.user_message,
        pending=set_pending_action,
    )

    if answer:
        return (answer, False)

    return None


def system_mode_guard_stage(context: ChatContext) -> StageResult:
    """В системном режиме не пускает обычные вопросы дальше."""

    if context.is_system_mode:
        return ("Нет такой системной команды.", False)

    return None


def web_search_stage(context: ChatContext) -> StageResult:
    """Ищет в интернете по явной просьбе пользователя."""

    search_query = extract_search_query(context.message)

    if search_query is None:
        return None

    if not is_module_enabled("internet"):
        return (
            "Модуль «Интернет» выключен. Включи его на панели "
            "под портретом — и я смогу искать.",
            True,
        )

    if not search_query:
        return (
            "Что именно найти? Напиши: "
            "«найди в интернете …».",
            True,
        )

    try:
        search_results = search_web(search_query)
    except WebSearchError as error:
        return (
            "Поиск в интернете не удался: "
            f"{error}.",
            True,
        )

    return (
        format_search_results(
            search_query,
            search_results,
        ),
        True,
    )


def help_stage(context: ChatContext) -> StageResult:
    """Показывает справку по командам и навыкам."""

    answer = get_help_response(context.message)

    if answer:
        return (answer, False)

    return None


def time_stage(context: ChatContext) -> StageResult:
    """Показывает локальные время, дату и день недели."""

    answer = get_time_and_date_response(context.message)

    if answer:
        return (answer, True)

    return None


def math_stage(context: ChatContext) -> StageResult:
    """Считает арифметическое выражение."""

    answer = get_math_response(context.message)

    if answer:
        return (answer, True)

    return None


def name_stage(context: ChatContext) -> StageResult:
    """Отвечает на вопросы об имени пользователя."""

    answer = get_name_response(context.message)

    if answer:
        return (answer, True)

    return None


def profile_stage(context: ChatContext) -> StageResult:
    """Отвечает на вопросы о профиле пользователя."""

    answer = get_profile_response(context.message)

    if answer:
        return (answer, True)

    return None


def intent_stage(context: ChatContext) -> StageResult:
    """Берёт точный ответ из intents.json."""

    reply = match_intent(context.message)

    if reply:
        return (reply.text, True)

    return None


def neural_stage(context: ChatContext) -> StageResult:
    """Отвечает локальной нейросетью, если она уверена."""

    reply = generate_answer(context.message)

    if reply:
        return (reply.text, True)

    return None


def helper_model_stage(context: ChatContext) -> StageResult:
    """Зовёт внешнюю модель, когда локальное ядро не уверено."""

    if not is_module_enabled("models"):
        return None

    try:
        helper = ask_helper(context.user_message)
    except OpenCodeError as error:
        message = describe_model_error("Помощь моделей", error)

        return CoreResponse(message, False, message)

    if helper is None:
        return None

    answer, model_name = helper

    return (
        f"{answer}\n\n(помогла модель {model_name})",
        False,
    )


def close_pattern_stage(context: ChatContext) -> StageResult:
    """Предлагает похожую известную фразу и ждёт подтверждения."""

    close_pattern = find_close_pattern(context.message)

    if not close_pattern:
        return None

    set_pending_clarification(close_pattern)

    return (
        "Возможно, ты имел "
        f"в виду: "
        f"«{close_pattern}»?",
        True,
    )


def unknown_stage(context: ChatContext) -> StageResult:
    """Сохраняет непонятую фразу и честно сообщает об этом."""

    add_unknown_message(context.user_message)

    return (
        "Я пока не знаю, как "
        "на это ответить. "
        "Я сохранил эту фразу, "
        "чтобы мы могли научить "
        "меня позже.",
        True,
    )


# Порядок важен: точное знание и служебные команды идут раньше
# нейросети и внешних моделей. Последний этап обрабатывает всё остальное.
STAGES: tuple[tuple[str, Stage], ...] = (
    ("identity", identity_stage),
    ("confirmation", confirmation_stage),
    ("system_command", system_command_stage),
    ("characteristics", characteristics_stage),
    ("clean_learned", clean_learned_stage),
    ("clear_variables", clear_variables_stage),
    ("show_variables", show_variables_stage),
    ("show_unknown", show_unknown_stage),
    ("learning", learning_stage),
    ("system_mode_guard", system_mode_guard_stage),
    ("web_search", web_search_stage),
    ("help", help_stage),
    ("time", time_stage),
    ("math", math_stage),
    ("name", name_stage),
    ("profile", profile_stage),
    ("intent", intent_stage),
    ("neural", neural_stage),
    ("helper_model", helper_model_stage),
    ("close_pattern", close_pattern_stage),
    ("unknown", unknown_stage),
)
