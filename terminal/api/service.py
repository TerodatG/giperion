# Giperion/terminal/api/service.py                                     v001
# Запуск задач агента без графического интерфейса.

from pathlib import Path

from terminal.api import api_config as config
from terminal.core.agent.loop import run_agent
from terminal.core.agent.native_brain import NativeBrain
from terminal.core.agent.providers import provider_chain
from terminal.core.agent.registry import all_specs
from terminal.core.agent.runs import read_runs
from terminal.core.app_version import current_version


class ApiError(RuntimeError):
    """Ошибка, которую API возвращает клиенту."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def build_brain():
    """Собирает «мозг» агента из настроек или переменных окружения."""

    provider = provider_chain()

    if provider is None:
        raise ApiError(
            "провайдер не настроен: заполни окно «Провайдер…» "
            "или задай AGENT_BASE_URL, AGENT_API_KEY, AGENT_MODEL",
            status=409,
        )

    return NativeBrain(provider)


def normalize_policy(policy: str) -> str:
    """Оставляет только известные режимы прав."""

    value = str(policy or "").strip().lower()

    if value in ("read", "confirm", "trust"):
        return value

    return "read"


def run_task(
    task: str,
    project: str = ".",
    steps: int = config.DEFAULT_STEPS,
    policy: str = "read",
    should_stop=None,
) -> dict:
    """Выполняет задачу и возвращает итог и трейс."""

    clean = str(task or "").strip()

    if not clean:
        raise ApiError("пустая задача")

    if len(clean) > config.MAX_TASK_CHARS:
        raise ApiError(
            f"задача длиннее {config.MAX_TASK_CHARS} символов"
        )

    try:
        limit = int(steps)
    except (TypeError, ValueError):
        limit = config.DEFAULT_STEPS

    limit = max(1, min(limit, config.MAX_STEPS))
    root = config.resolve_project(project)
    brain = build_brain()

    result = run_agent(
        clean,
        brain,
        Path(root),
        max_steps=limit,
        policy=normalize_policy(policy),
        should_stop=should_stop,
    )

    return {
        "ok": not result.cancelled and not result.error,
        "answer": str(result.answer or ""),
        "error": str(result.error or ""),
        "cancelled": bool(result.cancelled),
        "steps": [_step_payload(step) for step in result.steps],
        "usage": list(result.usage or []),
        "cost": _total_cost(brain, result.usage),
        "project": str(root),
        "version": current_version(),
    }


def _total_cost(brain, usage: list[dict] | None) -> float:
    """Суммарная стоимость прогона по расходу токенов."""

    from terminal.core.agent.cost import estimate_cost

    model = str(getattr(getattr(brain, "provider", None), "model", "") or "")

    if not model:
        import os

        model = os.environ.get("AGENT_MODEL", "").strip()

    return round(
        sum(estimate_cost(model, item) for item in (usage or [])),
        6,
    )


def _step_payload(step) -> dict:
    """Приводит шаг агента к JSON-виду."""

    return {
        "index": int(getattr(step, "index", 0)),
        "kind": str(getattr(step, "kind", "")),
        "title": str(getattr(step, "title", "")),
        "detail": str(getattr(step, "detail", ""))[:4000],
    }


def _json_safe(value):
    """Оставляет в аргументах только простые типы."""

    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return str(value)


def tools() -> list[str]:
    """Имена инструментов, доступных агенту."""

    return [spec.name for spec in all_specs()]


def recent_runs(limit: int = 20) -> list[dict]:
    """Последние прогоны из журнала."""

    try:
        return read_runs(max(1, min(int(limit), 200)))
    except (OSError, ValueError):
        return []
