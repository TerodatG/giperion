# Giperion/terminal/core/agent/loop.py                              v001
# Цикл агента: решение модели → инструмент → наблюдение → ответ.
# Последнее изменение: первый вариант — только чтение, лимит шагов.

from pathlib import Path
from typing import Callable

from terminal.core.agent.context import (
    MAX_PROMPT,
)
from terminal.core.agent.loop_helpers import (
    DEFAULT_MAX_STEPS,
    Brain,
    _append_chat_step,
    _compact_chat,  # noqa: F401 — реэкспорт для тестов
    _trim_chat,  # noqa: F401 — реэкспорт для тестов
    approval_key,  # noqa: F401 — реэкспорт для тестов
    render_plan,  # noqa: F401 — реэкспорт для тестов
)
from terminal.core.agent.loop_phases import (
    _calls_from,
    _create_state,
    _decide,
    _finish,
    _prepare_run,
    _reject_premature_answer,
    _step_note,
)
from terminal.core.agent.loop_tools import _execute_calls
from terminal.core.agent.protocol import (
    AgentResult,
    AgentStep,
    ApprovalRequest,
    ApprovalResult,
    ToolCall,
    ToolResult,
)

ROLE_HINTS = {
    "researcher": (
        "Ты исследователь: читай код и документацию, не меняй файлы. "
        "Верни точные пути, имена и факты."
    ),
    "reviewer": (
        "Ты проверяющий: ищи риски, противоречия и пропущенные случаи "
        "в решении. Не меняй файлы, перечисли замечания."
    ),
    "tester": (
        "Ты специалист по тестам: найди, какие тесты покрывают "
        "поведение и что стоит проверить. Файлы не меняй."
    ),
}


def _subagent_tasks(call: ToolCall) -> list[str]:
    """Список подзадач из аргументов: одна строка или массив."""

    tasks: list[str] = []
    raw = call.args.get("tasks")

    if isinstance(raw, list):
        tasks = [
            str(item).strip()
            for item in raw
            if isinstance(item, str) and item.strip()
        ]
    elif isinstance(raw, str) and raw.strip():
        tasks = [raw.strip()]

    single = str(call.args.get("task") or "").strip()

    if single and single not in tasks:
        tasks.insert(0, single)

    return tasks[:4]


def _run_parallel(
    run_one,
    tasks: list[str],
    should_stop: Callable[[], bool] | None,
) -> tuple[list[tuple[str, object]], bool]:
    """Параллельно выполняет подзадачи и умеет бросить их при отмене."""

    from concurrent.futures import (
        FIRST_COMPLETED,
        ThreadPoolExecutor,
        wait,
    )

    outcomes: list[tuple[str, object]] = []
    pool = ThreadPoolExecutor(max_workers=min(3, len(tasks)))
    futures = {pool.submit(run_one, task): task for task in tasks}
    interrupted = False

    try:
        while futures:
            if should_stop is not None and should_stop():
                interrupted = True

                for future in futures:
                    future.cancel()

                break

            done, _pending = wait(
                futures,
                timeout=0.2,
                return_when=FIRST_COMPLETED,
            )

            for future in done:
                task = futures.pop(future)

                try:
                    outcomes.append(future.result())
                except Exception as error:  # noqa: BLE001 — покажем в отчёте
                    outcomes.append(
                        (
                            task,
                            _FailedSubagent(
                                f"{type(error).__name__}: {error}"
                            ),
                        )
                    )
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    return outcomes, interrupted


class _FailedSubagent:
    """Заглушка результата, если подзадача упала с исключением."""

    def __init__(self, error: str) -> None:
        self.answer = ""
        self.cancelled = False
        self.error = error


def _run_subagent(
    call: ToolCall,
    brain: "Brain",
    root: Path,
    depth: int,
    allow_subagent: bool,
    should_stop: Callable[[], bool] | None,
    plan: list[dict] | None = None,
) -> ToolResult:
    """Запускает читающих подагентов; несколько — параллельно."""

    if depth >= 1 or not allow_subagent:
        return ToolResult(
            False,
            "Подагенты не могут вызывать других подагентов.",
        )

    tasks = _subagent_tasks(call)

    if not tasks:
        return ToolResult(False, "Подагенту не передана задача.")

    plan_prefix = ""

    if plan:
        plan_prefix = (
            "Общий план задачи:\n"
            + render_plan(plan)
            + "\n\nТвоя подзадача: "
        )

    role = str(call.args.get("role") or "").strip().lower()
    role_prefix = ""

    if role in ROLE_HINTS:
        role_prefix = ROLE_HINTS[role] + "\n\n"

    fork = getattr(brain, "fork", None)
    can_parallel = len(tasks) > 1 and callable(fork)

    def run_one(task: str) -> tuple[str, object]:
        sub_brain = fork() if callable(fork) else brain

        result = run_agent(
            role_prefix + plan_prefix + task,
            sub_brain,
            root,
            max_steps=4,
            should_stop=should_stop,
            require_tool_first=True,
            ground_first=True,
            approve=None,
            depth=depth + 1,
            allow_subagent=False,
            policy="read",
        )

        return task, result

    interrupted = False

    if can_parallel:
        outcomes, interrupted = _run_parallel(
            run_one,
            tasks,
            should_stop,
        )
    else:
        outcomes = [run_one(task) for task in tasks]

    parts = []
    answered = False

    for task, outcome in outcomes:
        if outcome.answer:
            answered = True
            text = outcome.answer
        elif outcome.cancelled:
            text = "остановлен"
        else:
            text = outcome.error or "не ответил"

        parts.append(f"Задача: {task}\nРезультат: {text}")

    if interrupted:
        parts.append(
            "Подагенты остановлены: часть подзадач не завершена."
        )

    return ToolResult(answered and not interrupted, "\n\n".join(parts))


def run_agent(
    task: str,
    brain: Brain,
    root: Path,
    max_steps: int = DEFAULT_MAX_STEPS,
    on_step: Callable[[AgentStep], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    require_tool_first: bool = True,
    ground_first: bool = True,
    approve: Callable[[ApprovalRequest], bool | ApprovalResult]
    | None = None,
    depth: int = 0,
    allow_subagent: bool = True,
    max_prompt_chars: int = MAX_PROMPT,
    policy: str = "confirm",
    initial_history: list[tuple[ToolCall, ToolResult]] | None = None,
    on_history: Callable[
        [list[tuple[ToolCall, ToolResult]]], None
    ] | None = None,
    allowed: set[str] | None = None,
    budget=None,
    step_timeout: float = 180.0,
) -> AgentResult:
    """Выполняет задачу по шагам и возвращает итог и трейс."""

    clean_task = str(task or "").strip()

    if not clean_task:
        return AgentResult(error="Пустая задача.")

    if policy not in ("read", "confirm", "trust"):
        policy = "confirm"

    native = bool(getattr(brain, "native", False))
    state = _create_state(
        initial_history=initial_history,
        allowed=allowed,
        on_step=on_step,
        on_history=on_history,
        should_stop=should_stop,
    )

    chat_mode = _prepare_run(
        state,
        task=clean_task,
        brain=brain,
        root=root,
        ground_first=ground_first,
    )

    for index in range(1, max(max_steps, 1) + 1):
        state.position = index

        if state.stopped():
            return AgentResult(
                steps=state.steps,
                cancelled=True,
                context_chars=state.context_peak,
            )

        outcome = _decide(
            state,
            index,
            task=clean_task,
            brain=brain,
            native=native,
            chat_mode=chat_mode,
            max_prompt_chars=max_prompt_chars,
            final_note=_step_note(index, max_steps, native),
            budget=budget,
            step_timeout=step_timeout,
        )

        if outcome is None:
            continue

        if isinstance(outcome, AgentResult):
            return outcome

        decision, assistant_raw = outcome

        if decision.action == "answer":
            if _reject_premature_answer(state, index, require_tool_first):
                continue

            state.emit(
                AgentStep(index, "answer", "Ответ", decision.text[:500])
            )

            return AgentResult(
                answer=decision.text,
                steps=state.steps,
                context_chars=state.context_peak,
            )

        calls = _calls_from(decision)

        if not calls:
            continue

        step_start = len(state.history)

        _execute_calls(
            state,
            index,
            calls,
            brain=brain,
            root=root,
            policy=policy,
            approve=approve,
            depth=depth,
            allow_subagent=allow_subagent,
            should_stop=should_stop,
            subagent_runner=_run_subagent,
            subagent_tasks=_subagent_tasks,
        )

        if chat_mode:
            _append_chat_step(
                state.chat,
                assistant_raw,
                state.history[step_start:],
            )

    return _finish(
        state,
        task=clean_task,
        brain=brain,
        native=native,
        chat_mode=chat_mode,
        max_prompt_chars=max_prompt_chars,
        max_steps=max_steps,
        budget=budget,
    )
