# Giperion/terminal/core/agent/settings.py                           v001
# Настройки провайдера агента и выбор источника: файл или окружение.
# Последнее изменение: первый вариант — base_url, ключ и модель.

import os
from pathlib import Path

from config import DATA_DIR
from shared.storage.json_store import read_json_object, update_json

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


def _update_fields(values: dict[str, object]) -> None:
    """Меняет несколько полей настроек под блокировкой файла."""

    def mutate(document: dict) -> dict:
        document.update(values)

        return document

    update_json(SETTINGS_FILE, mutate, default={})


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

    _update_fields(values)

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


def settings_file() -> Path:
    """Путь к файлу настроек агента."""

    return SETTINGS_FILE


def plugins_enabled() -> bool:
    """Разрешены ли сторонние плагины инструментов (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("plugins_enabled") is True


def set_plugins_enabled(enabled: bool) -> None:
    """Включает или выключает плагины в настройках агента."""

    _update_fields({"plugins_enabled": bool(enabled)})


def stream_enabled() -> bool:
    """Показывать ли ответ модели по мере генерации (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("stream_enabled") is True


def set_stream_enabled(enabled: bool) -> None:
    """Включает или выключает потоковый ответ."""

    _update_fields({"stream_enabled": bool(enabled)})


def allow_unsafe_plugins() -> bool:
    """Разрешены ли плагинам сеть и запуск программ (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("unsafe_plugins") is True


def set_allow_unsafe_plugins(enabled: bool) -> None:
    """Разрешает или запрещает опасные разрешения плагинов."""

    _update_fields({"unsafe_plugins": bool(enabled)})


def mcp_enabled() -> bool:
    """Включены ли MCP-серверы (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("mcp_enabled") is True


def set_mcp_enabled(enabled: bool) -> None:
    """Включает или выключает MCP-серверы."""

    _update_fields({"mcp_enabled": bool(enabled)})


def browser_enabled() -> bool:
    """Разрешено ли агенту читать веб-страницы (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("browser_enabled") is True


def set_browser_enabled(enabled: bool) -> None:
    """Включает или выключает чтение веб-страниц."""

    _update_fields({"browser_enabled": bool(enabled)})


def browser_js_enabled() -> bool:
    """Разрешён ли браузер с JavaScript (по умолчанию нет)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("browser_js_enabled") is True


def set_browser_js_enabled(enabled: bool) -> None:
    """Включает или выключает браузер с JavaScript."""

    _update_fields({"browser_js_enabled": bool(enabled)})


def browser_session_enabled() -> bool:
    """Держать ли один Chromium на задачу (по умолчанию да)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("browser_session") is not False


def set_browser_session_enabled(enabled: bool) -> None:
    """Включает или выключает одну браузерную сессию на задачу."""

    _update_fields({"browser_session": bool(enabled)})


def egress_domains() -> tuple[str, ...]:
    """Общий allowlist доменов; пусто — разрешены все публичные."""

    document = read_json_object(SETTINGS_FILE)
    raw = document.get("egress_domains")

    if not isinstance(raw, list):
        return ()

    result: list[str] = []
    seen: set[str] = set()

    for item in raw:
        if not isinstance(item, str):
            continue

        name = item.strip().lower().strip(".")

        if not name or name in seen:
            continue

        seen.add(name)
        result.append(name)

    return tuple(result)


def set_egress_domains(domains: list[str]) -> None:
    """Сохраняет общий allowlist доменов."""

    _update_fields(
        {
            "egress_domains": [
                str(item).strip().lower()
                for item in domains
                if str(item).strip()
            ]
        }
    )


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

    _update_fields({"max_steps": min(40, max(1, int(steps)))})


def model_choice() -> str:
    """Выбранная в окне агента модель: 'native' или id из каталога."""

    document = read_json_object(SETTINGS_FILE)
    value = document.get("model_choice")

    return value.strip() if isinstance(value, str) else ""


def set_model_choice(choice: str) -> None:
    """Запоминает выбор модели в окне агента."""

    _update_fields(
        {"model_choice": str(choice or "").strip()[:120]}
    )


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

    _update_fields({"plugin_sandbox": mode})


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

    _update_fields({"approval_policy": policy})


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

    _update_fields(
        {
            "token_limit": max(0, int(tokens)),
            "cost_limit": max(0.0, float(cost)),
            "price_in": max(0.0, float(price_in)),
            "price_out": max(0.0, float(price_out)),
        }
    )


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

    _update_fields(
        {
            "context_chars": min(
                2_000_000,
                max(8_000, int(chars)),
            )
        }
    )


def context_auto() -> bool:
    """Считать бюджет из контекста модели (по умолчанию да)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("context_auto") is not False


def set_context_auto(enabled: bool) -> None:
    """Включает или выключает автоматический бюджет."""

    _update_fields({"context_auto": bool(enabled)})


def semantic_enabled() -> bool:
    """Использовать ли смысловой поиск в задачах (по умолчанию да)."""

    document = read_json_object(SETTINGS_FILE)

    return document.get("semantic_search") is not False


def set_semantic_enabled(enabled: bool) -> None:
    """Включает или выключает смысловой поиск."""

    _update_fields({"semantic_search": bool(enabled)})


def embedding_model() -> str:
    """Модель эмбеддингов; пусто — определить автоматически."""

    document = read_json_object(SETTINGS_FILE)

    return str(document.get("embedding_model") or "").strip()


def set_embedding_model(name: str) -> None:
    """Сохраняет имя модели эмбеддингов."""

    _update_fields({"embedding_model": str(name or "").strip()})


def request_timeout() -> int:
    """Таймаут одного запроса к провайдеру в секундах."""

    document = read_json_object(SETTINGS_FILE)
    value = _number(document, "request_timeout", DEFAULT_TIMEOUT, as_int=True)

    return min(900, max(10, int(value)))


def set_request_timeout(seconds: int) -> None:
    """Сохраняет таймаут запроса."""

    _update_fields(
        {"request_timeout": min(900, max(10, int(seconds)))}
    )


DEFAULT_STEP_TIMEOUT = 180


def step_timeout() -> int:
    """Сколько секунд отводится на один шаг модели (0 — без лимита)."""

    document = read_json_object(SETTINGS_FILE)
    value = _number(
        document,
        "step_timeout",
        DEFAULT_STEP_TIMEOUT,
        as_int=True,
    )

    return min(3600, max(0, int(value)))


def set_step_timeout(seconds: int) -> None:
    """Сохраняет таймаут шага."""

    _update_fields(
        {"step_timeout": min(3600, max(0, int(seconds)))}
    )
