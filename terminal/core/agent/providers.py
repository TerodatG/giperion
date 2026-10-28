# Giperion/terminal/core/agent/providers.py                           v002
# Совместимый фасад провайдера и мозга; код в provider_http/native_brain.
# Последнее изменение: разнесено на HTTP-провайдера и NativeBrain.

from terminal.core.agent import settings
from terminal.core.agent.native_brain import NativeBrain
from terminal.core.agent.provider_http import (
    OpenAICompatibleProvider,
    ProviderError,
    ProviderReply,
    ProviderRetry,
    _http_message,  # noqa: F401 — реэкспорт для тестов
    _merge_name,  # noqa: F401 — реэкспорт для тестов
    _offline_message,  # noqa: F401 — реэкспорт для тестов
    _retry_after,  # noqa: F401 — реэкспорт для тестов
)

__all__ = [
    "NativeBrain",
    "OpenAICompatibleProvider",
    "ProviderError",
    "ProviderReply",
    "ProviderRetry",
    "anthropic_from_env",
    "provider_chain",
    "provider_from_env",
    "provider_from_settings",
]


def provider_from_env() -> OpenAICompatibleProvider | None:
    """Собирает провайдера из переменных окружения, если они заданы."""

    import os

    base_url = os.environ.get("AGENT_BASE_URL", "").strip()
    api_key = os.environ.get("AGENT_API_KEY", "").strip()
    model = os.environ.get("AGENT_MODEL", "").strip()

    if not (base_url and api_key and model):
        return None

    return OpenAICompatibleProvider(base_url, api_key, model)


def provider_from_settings() -> OpenAICompatibleProvider | None:
    """Собирает провайдера из файла/окружения или возвращает None."""

    values = settings.resolve_provider_values()

    if not settings.has_settings(values):
        return None

    return OpenAICompatibleProvider(
        values["base_url"],
        values["api_key"],
        values["model"],
        timeout=settings.request_timeout(),
        stream=settings.stream_enabled(),
    )


def anthropic_from_env():
    """Запасной провайдер Anthropic из переменных окружения."""

    import os

    from terminal.core.agent.provider_anthropic import AnthropicProvider

    base_url = os.environ.get("AGENT_FALLBACK_BASE_URL", "").strip()
    api_key = os.environ.get("AGENT_FALLBACK_API_KEY", "").strip()
    model = os.environ.get("AGENT_FALLBACK_MODEL", "").strip()

    if not (base_url and api_key and model):
        return None

    return AnthropicProvider(base_url, api_key, model)


def provider_chain():
    """Основной провайдер и, если задан, запасной Anthropic."""

    from terminal.core.agent.provider_router import FallbackProvider

    primary = provider_from_settings() or provider_from_env()

    if primary is None:
        return None

    fallback = anthropic_from_env()

    if fallback is None:
        return primary

    return FallbackProvider(primary, fallback)
