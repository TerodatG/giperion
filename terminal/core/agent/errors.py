# Giperion/terminal/core/agent/errors.py                               v001
# Классы ошибок агента: повторить, спросить, остановить.
# Последнее изменение: первый вариант — стратегии и classify.

RETRY = "retry"
ASK = "ask"
STOP = "stop"


class AgentError(RuntimeError):
    """Базовая ошибка с политикой обработки."""

    strategy = STOP


class RetryableError(AgentError):
    """Временная ошибка: шаг можно повторить."""

    strategy = RETRY


class AskUserError(AgentError):
    """Нужно решение пользователя."""

    strategy = ASK


class FatalError(AgentError):
    """Продолжать нельзя."""

    strategy = STOP


def classify(error: BaseException) -> str:
    """Стратегия для исключения."""

    if isinstance(error, AgentError):
        return str(error.strategy)

    return STOP
