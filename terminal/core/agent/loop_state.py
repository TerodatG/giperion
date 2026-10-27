# Giperion/terminal/core/agent/loop_state.py                         v001
# Состояние прогона и стартовое чтение проекта.
# Последнее изменение: вынесено из loop_phases.

from pathlib import Path
from typing import Callable

from terminal.core.agent import registry
from terminal.core.agent.guard import find_instructions, mark_untrusted
from terminal.core.agent.loop_helpers import (
    Brain,
    _call_detail,
    _call_title,
    _observation_block,
    grounding_calls,
)
from terminal.core.agent.protocol import (
    AgentStep,
    ToolCall,
    ToolResult,
)
from terminal.core.agent.redact import redact

# Инструменты, которые действительно дают факты о проекте. Служебные
# псевдо-вызовы policy/format сюда не входят: иначе требование
# «сначала прочитай» обходится одним отказом.
READ_TOOLS = frozenset(
    {
        "list_dir",
        "read_file",
        "find_symbol",
        "search_text",
        "git_status",
        "git_diff",
        "git_log",
        "ask_subagent",
    }
)


class _RunState:
    """Изменяемое состояние прогона: шаги, история и разрешения."""

    def __init__(
        self,
        *,
        steps: list[AgentStep],
        history: list[tuple[ToolCall, ToolResult]],
        remembered: set[str],
        on_step: Callable[[AgentStep], None] | None,
        on_history: Callable[
            [list[tuple[ToolCall, ToolResult]]], None
        ] | None,
        should_stop: Callable[[], bool] | None,
    ) -> None:
        self.steps = steps
        self.history = history
        self.remembered = remembered
        self.on_step = on_step
        self.on_history = on_history
        self.should_stop = should_stop
        self.position = 0
        self.context_peak = 0
        self.root: Path | None = None
        self.budget_warned = False
        self.usage: list[dict] = []
        self.last_tokens = 0
        self.last_cost = 0.0
        self.chat: list[dict] = []
        self.read_ok = False
        self.plan: list[dict] = []
        self.tool_calls = 0
        self.network_calls = 0
        self.write_calls = 0

    def remember(self, call: ToolCall, result: ToolResult) -> None:
        """Чистит наблюдение от секретов и внедрённых инструкций."""

        clean = redact(result.text)

        if clean.hidden:
            result = ToolResult(result.ok, clean.text)

            self.emit(
                AgentStep(
                    self.position,
                    "secret",
                    "Секреты скрыты",
                    f"скрыто фрагментов: {clean.hidden} · "
                    f"{call.tool}",
                )
            )

        flags = find_instructions(result.text)

        if flags:
            result = ToolResult(
                result.ok,
                mark_untrusted(result.text, flags),
            )

            self.emit(
                AgentStep(
                    self.position,
                    "security",
                    "Похоже на внедрение инструкций",
                    f"{call.tool}: " + ", ".join(flags[:5]),
                )
            )

        self.history.append((call, result))

        if self.on_history is not None:
            self.on_history(self.history)

    def emit(self, step: AgentStep) -> None:
        """Добавляет шаг в трейс и отдаёт его окну."""

        self.steps.append(step)

        if self.on_step is not None:
            self.on_step(step)

    def stopped(self) -> bool:
        """Просили ли остановить задачу."""

        return bool(self.should_stop and self.should_stop())


def _create_state(
    *,
    initial_history: list[tuple[ToolCall, ToolResult]] | None,
    allowed: set[str] | None,
    on_step: Callable[[AgentStep], None] | None,
    on_history: Callable[
        [list[tuple[ToolCall, ToolResult]]], None
    ] | None,
    should_stop: Callable[[], bool] | None,
) -> _RunState:
    """Создаёт состояние прогона и чистит начальную историю."""

    steps: list[AgentStep] = []
    history: list[tuple[ToolCall, ToolResult]] = [
        (call, ToolResult(result.ok, redact(result.text).text))
        for call, result in (initial_history or [])
    ]

    state = _RunState(
        steps=steps,
        history=history,
        remembered=allowed if allowed is not None else set(),
        on_step=on_step,
        on_history=on_history,
        should_stop=should_stop,
    )
    state.read_ok = any(
        call.tool in READ_TOOLS and result.ok
        for call, result in history
    )

    return state


def _prepare_run(
    state: _RunState,
    *,
    task: str,
    brain: Brain,
    root: Path,
    ground_first: bool,
) -> bool:
    """Делает стартовое чтение и открывает переписку; True — chat-режим."""

    state.root = Path(root).resolve()
    brain.root = state.root

    if ground_first and not state.history:
        for call in grounding_calls(task, root):
            result = registry.execute(root, call)

            state.emit(
                AgentStep(
                    0,
                    "tool",
                    "старт · " + _call_title(call),
                    _call_detail(result),
                )
            )

            state.remember(call, result)

            if call.tool in READ_TOOLS and result.ok:
                state.read_ok = True

    chat_mode = bool(
        getattr(brain, "messages_mode", False)
        and callable(getattr(brain, "decide_chat", None))
    )

    if chat_mode:
        state.chat = brain.begin(
            task,
            [
                _observation_block(call, result)
                for call, result in state.history[-4:]
            ],
        )

    return chat_mode
