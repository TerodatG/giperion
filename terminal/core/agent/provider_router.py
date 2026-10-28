# Giperion/terminal/core/agent/provider_router.py                      v001
# Резервный провайдер: основная модель, затем запасная.

from terminal.core.agent.provider_http import ProviderError, ProviderReply

# Сколько раз пробовать запасной провайдер, если основной упал.
DEFAULT_ATTEMPTS = 1


class FallbackProvider:
    """Пробует основной провайдер, при сбое — запасной.

    Интерфейс совпадает с обычным провайдером: `complete(messages, tools)`.
    После вызова `used` показывает, кто ответил: "primary" или "fallback".
    """

    def __init__(self, primary, secondary=None, attempts: int = DEFAULT_ATTEMPTS) -> None:
        self.primary = primary
        self.secondary = secondary
        self.attempts = max(1, int(attempts))
        self.used = "primary"
        self.last_error: Exception | None = None

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        on_delta=None,
    ) -> ProviderReply:
        """Отвечает основным провайдером, при ошибке — запасным."""

        try:
            reply = self.primary.complete(messages, tools, on_delta)
            self.used = "primary"
            self.last_error = None

            return reply
        except ProviderError as error:
            self.last_error = error

        if self.secondary is None:
            raise ProviderError(str(self.last_error)) from self.last_error

        reply = self.secondary.complete(messages, tools, on_delta)
        self.used = "fallback"

        return reply
