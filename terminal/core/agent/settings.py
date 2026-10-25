# Giperion/terminal/core/agent/settings.py                           v001
# Настройки провайдера агента и выбор источника: файл или окружение.
# Последнее изменение: первый вариант — base_url, ключ и модель.

import os
from pathlib import Path

from config import DATA_DIR
from shared.storage.json_store import read_json_object, write_json

SETTINGS_FILE = DATA_DIR / "agent_settings.json"

EMPTY = {
    "base_url": "",
    "api_key": "",
    "model": "",
}


def load_settings() -> dict[str, str]:
    """Читает настройки провайдера; битые поля заменяются пустыми."""

    document = read_json_object(SETTINGS_FILE)
    result = dict(EMPTY)

    for key in EMPTY:
        value = document.get(key)

        if isinstance(value, str):
            result[key] = value.strip()

    return result


def save_settings(
    base_url: str,
    api_key: str,
    model: str,
) -> dict[str, str]:
    """Сохраняет настройки провайдера в gitignored-файл."""

    values = {
        "base_url": str(base_url or "").strip(),
        "api_key": str(api_key or "").strip(),
        "model": str(model or "").strip(),
    }

    document = read_json_object(SETTINGS_FILE)
    document.update(values)
    write_json(SETTINGS_FILE, document)

    return values


def has_settings(values: dict[str, str] | None = None) -> bool:
    """Заполнены ли все три поля провайдера."""

    data = values if values is not None else load_settings()

    return all(bool(data.get(key)) for key in EMPTY)


def mask_key(key: str) -> str:
    """Прячет ключ, оставляя последние четыре символа."""

    text = str(key or "")

    if len(text) <= 4:
        return "•" * len(text)

    return "•" * (len(text) - 4) + text[-4:]


def env_provider_values() -> dict[str, str]:
    """Значения провайдера из переменных окружения."""

    return {
        "base_url": os.environ.get("AGENT_BASE_URL", "").strip(),
        "api_key": os.environ.get("AGENT_API_KEY", "").strip(),
        "model": os.environ.get("AGENT_MODEL", "").strip(),
    }


def resolve_provider_values() -> dict[str, str]:
    """Настройки из файла важнее окружения; иначе окружение."""

    stored = load_settings()

    if has_settings(stored):
        return stored

    return env_provider_values()


def provider_from_settings():
    """Собирает провайдера из файла/окружения или возвращает None."""

    from terminal.core.agent.providers import (
        OpenAICompatibleProvider,
    )

    values = resolve_provider_values()

    if not has_settings(values):
        return None

    return OpenAICompatibleProvider(
        values["base_url"],
        values["api_key"],
        values["model"],
        timeout=request_timeout(),
        stream=stream_enabled(),
    )


def settings_file() -> Path:
    """Путь к файлу настроек агента."""

    return SETTINGS_FILE


def plugins_enabled() -> bool:
    """Разрешены ли сторонние плагины инструментов (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("plugins_enabled") is True


def set_plugins_enabled(enabled: bool) -> None:
    """Включает или выключает плагины в настройках агента."""

    document = read_json_object(SETTINGS_FILE)
    document["plugins_enabled"] = bool(enabled)
    write_json(SETTINGS_FILE, document)


def stream_enabled() -> bool:
    """Показывать ли ответ модели по мере генерации (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("stream_enabled") is True


def set_stream_enabled(enabled: bool) -> None:
    """Включает или выключает потоковый ответ."""

    document = read_json_object(SETTINGS_FILE)
    document["stream_enabled"] = bool(enabled)
    write_json(SETTINGS_FILE, document)


def allow_unsafe_plugins() -> bool:
    """Разрешены ли плагинам сеть и запуск программ (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("unsafe_plugins") is True


def set_allow_unsafe_plugins(enabled: bool) -> None:
    """Разрешает или запрещает опасные разрешения плагинов."""

    document = read_json_object(SETTINGS_FILE)
    document["unsafe_plugins"] = bool(enabled)
    write_json(SETTINGS_FILE, document)


def mcp_enabled() -> bool:
    """Включены ли MCP-серверы (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("mcp_enabled") is True


def set_mcp_enabled(enabled: bool) -> None:
    """Включает или выключает MCP-серверы."""

    document = read_json_object(SETTINGS_FILE)
    document["mcp_enabled"] = bool(enabled)
    write_json(SETTINGS_FILE, document)


def browser_enabled() -> bool:
    """Разрешено ли агенту читать веб-страницы (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("browser_enabled") is True


def set_browser_enabled(enabled: bool) -> None:
    """Включает или выключает чтение веб-страниц."""

    document = read_json_object(SETTINGS_FILE)
    document["browser_enabled"] = bool(enabled)
    write_json(SETTINGS_FILE, document)


DEFAULT_MAX_STEPS = 12


def max_steps() -> int:
    """Сколько шагов разрешено одной задаче."""

    document = read_json_object(SETTINGS_FILE)
    value = _number(
        document,
        "max_steps",
        DEFAULT_MAX_STEPS,
        as_int=True,
    )

    return min(40, max(1, int(value)))


def set_max_steps(steps: int) -> None:
    """Сохраняет лимит шагов задачи."""

    document = read_json_object(SETTINGS_FILE)
    document["max_steps"] = min(40, max(1, int(steps)))
    write_json(SETTINGS_FILE, document)


def model_choice() -> str:
    """Выбранная в окне агента модель: 'native' или id из каталога."""

    document = read_json_object(SETTINGS_FILE)
    value = document.get("model_choice")

    return value.strip() if isinstance(value, str) else ""


def set_model_choice(choice: str) -> None:
    """Запоминает выбор модели в окне агента."""

    document = read_json_object(SETTINGS_FILE)
    document["model_choice"] = str(choice or "").strip()[:120]
    write_json(SETTINGS_FILE, document)


SANDBOX_MODES = ("process", "appcontainer")


def plugin_sandbox() -> str:
    """Режим изоляции плагинов: процесс или AppContainer."""

    document = read_json_object(SETTINGS_FILE)
    value = document.get("plugin_sandbox")

    return value if value in SANDBOX_MODES else "process"


def set_plugin_sandbox(mode: str) -> None:
    """Сохраняет режим изоляции плагинов."""

    if mode not in SANDBOX_MODES:
        raise ValueError(f"Неизвестный режим песочницы: {mode}")

    document = read_json_object(SETTINGS_FILE)
    document["plugin_sandbox"] = mode
    write_json(SETTINGS_FILE, document)


POLICIES = ("read", "confirm", "trust")

def approval_policy() -> str:
    """Возвращает политику подтверждений (по умолчанию confirm)."""

    document = read_json_object(SETTINGS_FILE)
    value = document.get("approval_policy")

    return value if value in POLICIES else "confirm"


def set_approval_policy(policy: str) -> None:
    """Сохраняет политику подтверждений."""

    if policy not in POLICIES:
        raise ValueError(f"Неизвестная политика: {policy}")

    document = read_json_object(SETTINGS_FILE)
    document["approval_policy"] = policy
    write_json(SETTINGS_FILE, document)


def _number(
    document: dict,
    key: str,
    default: float,
    as_int: bool = False,
) -> float | int:
    """Число из файла настроек; мусор заменяется значением по умолчанию."""

    value = document.get(key)

    if isinstance(value, bool):
        return int(default) if as_int else default

    try:
        number = float(value)
    except (TypeError, ValueError):
        return int(default) if as_int else default

    if number < 0:
        return int(default) if as_int else default

    return int(number) if as_int else number


def budget_limits():
    """Лимиты и цены задачи из файла настроек."""

    from terminal.core.agent.budget import BudgetLimits

    document = read_json_object(SETTINGS_FILE)

    return BudgetLimits(
        tokens=_number(document, "token_limit", 0, as_int=True),
        cost=_number(document, "cost_limit", 0.0),
        price_in=_number(document, "price_in", 0.0),
        price_out=_number(document, "price_out", 0.0),
    )


def save_budget_limits(
    tokens: int,
    cost: float,
    price_in: float,
    price_out: float,
) -> None:
    """Сохраняет лимиты задачи; отрицательные значения приводятся к нулю."""

    document = read_json_object(SETTINGS_FILE)
    document["token_limit"] = max(0, int(tokens))
    document["cost_limit"] = max(0.0, float(cost))
    document["price_in"] = max(0.0, float(price_in))
    document["price_out"] = max(0.0, float(price_out))
    write_json(SETTINGS_FILE, document)


DEFAULT_TIMEOUT = 120
DEFAULT_CONTEXT_CHARS = 60_000


def context_limit_chars() -> int:
    """Бюджет промпта в символах (настраивается под модель)."""

    document = read_json_object(SETTINGS_FILE)
    value = _number(
        document,
        "context_chars",
        DEFAULT_CONTEXT_CHARS,
        as_int=True,
    )

    return min(2_000_000, max(8_000, int(value)))


def set_context_limit_chars(chars: int) -> None:
    """Сохраняет бюджет промпта в символах."""

    document = read_json_object(SETTINGS_FILE)
    document["context_chars"] = min(
        2_000_000,
        max(8_000, int(chars)),
    )
    write_json(SETTINGS_FILE, document)


def request_timeout() -> int:
    """Таймаут одного запроса к провайдеру в секундах."""

    document = read_json_object(SETTINGS_FILE)
    value = _number(document, "request_timeout", DEFAULT_TIMEOUT, as_int=True)

    return min(900, max(10, int(value)))


def set_request_timeout(seconds: int) -> None:
    """Сохраняет таймаут запроса."""

    document = read_json_object(SETTINGS_FILE)
    document["request_timeout"] = min(900, max(10, int(seconds)))
    write_json(SETTINGS_FILE, document)
