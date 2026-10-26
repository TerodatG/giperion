# Giperion/tools/eval_runner.py                                       v001
# Прогон одной задачи в worktree и выбор модели стенда.
# Последнее изменение: вынесено из eval_agent.

import time
from contextlib import nullcontext
from pathlib import Path

from terminal.core.agent.brain import ModelBrain
from terminal.core.agent.loop import run_agent
from terminal.core.agent.providers import (
    NativeBrain,
    provider_from_settings,
)
from terminal.core.agent.settings import (
    context_limit_chars,
    step_timeout,
)
from terminal.core.agent.worktrees import (
    WorktreeError,
    create_worktree,
    remove_worktree,
)
from terminal.core.helper_model import get_helper_model
from tools.eval_tasks import EvalTask

FATAL_MARKERS = (
    "usage limit",
    "limit reached",
    "quota",
    "insufficient",
    "неверный ключ",
    "unauthorized",
    "forbidden",
    "401",
    "403",
)


def is_fatal(error: str) -> bool:
    """Ошибка провайдера, после которой нет смысла гонять остальные задачи."""

    text = str(error or "").casefold()

    return any(marker in text for marker in FATAL_MARKERS)


def build_brain(model: str, provider: str):
    """Выбирает провайдера: аргументы, настройки, помощник."""

    if model:
        return (
            ModelBrain(model, provider or "opencode"),
            f"{provider or 'opencode'}/{model}",
        )

    native = provider_from_settings()

    if native is not None:
        from terminal.core.agent.settings import budget_limits

        limits = budget_limits()

        return NativeBrain(native, limits), f"native/{native.model}"

    helper = get_helper_model()

    if helper is None:
        raise SystemExit(
            "Нет модели: задай --model/--provider или настрой провайдера."
        )

    return (
        ModelBrain(
            helper["model_id"],
            helper.get("provider_id") or "opencode",
        ),
        helper["name"],
    )


def run_task(task: EvalTask, brain, base: Path) -> dict:
    """Выполняет задачу в отдельном worktree и проверяет результат."""

    folder, branch = create_worktree(
        base,
        f"eval-{task.id}-{int(time.time())}",
    )

    try:
        if task.setup is not None:
            task.setup(folder)

        approvals: list = []
        started = time.monotonic()
        before_tokens = int(getattr(brain, "total_tokens", 0) or 0)
        before_cost = float(getattr(brain, "cost", 0.0) or 0.0)

        context = (
            task.prepare(folder)
            if task.prepare is not None
            else nullcontext()
        )

        with context:
            result = run_agent(
                task.task,
                brain,
                folder,
                max_steps=task.max_steps,
                ground_first=True,
                approve=lambda request: approvals.append(request) or True,
                max_prompt_chars=context_limit_chars(),
                step_timeout=step_timeout(),
            )

        duration = time.monotonic() - started

        if task.inspect is not None:
            ok, note = task.inspect(folder, result)
        else:
            ok, note = task.check(folder, result.answer)
        tokens = int(getattr(brain, "total_tokens", 0) or 0) - before_tokens
        cost = float(getattr(brain, "cost", 0.0) or 0.0) - before_cost

        return {
            "id": task.id,
            "title": task.title,
            "ok": bool(ok),
            "note": note,
            "steps": len(result.steps),
            "approvals": len(approvals),
            "duration_s": round(duration, 2),
            "context_chars": result.context_chars,
            "tokens": max(0, tokens),
            "cost": round(max(0.0, cost), 6),
            "answer": result.answer[:500],
            "error": result.error[:300],
        }
    finally:
        try:
            remove_worktree(base, folder, branch)
        except WorktreeError:
            pass
