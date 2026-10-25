# Giperion/terminal/core/agent/loop_phases.py                         v001
# Фазы прогона: состояние, старт, решение, отказ и итог.
# Последнее изменение: вынесено из loop.

from pathlib import Path
from typing import Callable

from terminal.core.agent import registry
from terminal.core.agent.context import (
    DecisionError,
    build_native_prompt,
    build_prompt,
    is_within_budget,
    parse_decision,
)
from terminal.core.agent.guard import find_instructions, mark_untrusted
from terminal.core.agent.loop_helpers import (
    Brain,
    _call_detail,
    _call_title,
    _chat_chars,
    _compact_chat,
    _observation_block,
    _trim_chat,
    budget_state,
    grounding_calls,
)
from terminal.core.agent.protocol import (
    AgentDecision,
    AgentResult,
    AgentStep,
    ToolCall,
    ToolResult,
)
from terminal.core.agent.redact import redact


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
        self.chat: list[dict] = []

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

    return _RunState(
        steps=steps,
        history=history,
        remembered=allowed if allowed is not None else set(),
        on_step=on_step,
        on_history=on_history,
        should_stop=should_stop,
    )


def _prepare_run(
    state: _RunState,
    *,
    task: str,
    brain: Brain,
    root: Path,
    ground_first: bool,
) -> bool:
    """Делает стартовое чтение и открывает переписку; True — chat-режим."""

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


def _step_note(index: int, max_steps: int, native: bool) -> str:
    """Подсказка модели на последний шаг."""

    if index < max(max_steps, 1):
        return ""

    if native:
        return (
            "Это последний шаг, инструменты больше не выполняются. "
            "Дай ответ по тому, что уже есть в истории, и честно "
            "скажи, чего не хватило."
        )

    return (
        "Это последний шаг, инструменты больше не выполняются. "
        'Верни {"action": "answer", "text": "..."} по тому, '
        "что уже есть в истории."
    )


def _calls_from(decision: AgentDecision) -> list[ToolCall]:
    """Все вызовы решения: одиночный и пакет."""

    calls = list(decision.calls)

    if decision.call is not None:
        calls.append(decision.call)

    return calls


def _reject_premature_answer(
    state: _RunState,
    index: int,
    require_tool_first: bool,
) -> bool:
    """Не даёт ответить до первого чтения; True — шаг отклонён."""

    if not require_tool_first or state.history:
        return False

    state.emit(
        AgentStep(
            index,
            "error",
            "Нужен шаг чтения",
            "Модель ответила, ничего не прочитав.",
        )
    )
    state.remember(
        ToolCall(tool="policy", args={}),
        ToolResult(
            False,
            "Сначала вызови list_dir, read_file или "
            "search_text, а потом отвечай.",
        ),
    )

    return True


def _decide(
    state: _RunState,
    index: int,
    *,
    task: str,
    brain: Brain,
    native: bool,
    chat_mode: bool,
    max_prompt_chars: int,
    final_note: str,
    budget,
) -> AgentResult | tuple[AgentDecision, dict] | None:
    """Спрашивает модель и проверяет бюджет шага."""

    prompt_builder = build_native_prompt if native else build_prompt

    assistant_raw: dict = {}

    if chat_mode:
        _compact_chat(state.chat)
        state.context_peak = max(state.context_peak, _chat_chars(state.chat))

        if _chat_chars(state.chat) > max_prompt_chars:
            state.chat = _trim_chat(state.chat, max_prompt_chars)
            state.context_peak = max(state.context_peak, _chat_chars(state.chat))

        if _chat_chars(state.chat) > max_prompt_chars:
            return AgentResult(
                steps=state.steps,
                error=(
                    "Контекст превысил бюджет "
                    f"{max_prompt_chars} символов."
                ),
                context_chars=state.context_peak,
            )

        try:
            decision, assistant_raw = brain.decide_chat(state.chat)
        except Exception as error:  # noqa: BLE001 — покажем в трейсе
            state.emit(
                AgentStep(
                    index,
                    "error",
                    "Модель не ответила",
                    f"{type(error).__name__}: {error}",
                )
            )

            return AgentResult(
                steps=state.steps,
                error=f"Модель не ответила: {error}",
                context_chars=state.context_peak,
            )
    else:
        prompt = prompt_builder(
            task,
            state.history,
            max_chars=max_prompt_chars,
            final_note=final_note,
        )
        state.context_peak = max(state.context_peak, len(prompt))

        if not is_within_budget(prompt, max_prompt_chars):
            return AgentResult(
                steps=state.steps,
                error=(
                    "Контекст превысил бюджет "
                    f"{max_prompt_chars} символов."
                ),
                context_chars=state.context_peak,
            )

        try:
            raw = brain.decide(prompt)
        except Exception as error:  # noqa: BLE001 — покажем в трейсе
            state.emit(
                AgentStep(
                    index,
                    "error",
                    "Модель не ответила",
                    f"{type(error).__name__}: {error}",
                )
            )

            return AgentResult(
                steps=state.steps,
                error=f"Модель не ответила: {error}",
                context_chars=state.context_peak,
            )

    if not chat_mode:
        try:
            decision = (
                raw
                if isinstance(raw, AgentDecision)
                else parse_decision(raw)
            )
        except DecisionError as error:
            state.emit(
                AgentStep(
                    index,
                    "error",
                    "Некорректное решение",
                    str(error),
                )
            )

            state.remember(
                ToolCall(tool="format", args={}),
                ToolResult(
                    False,
                    "Ответ не разобрался: "
                    f"{error}. Верни только JSON по схеме.",
                ),
            )

            return None

    tokens, cost, budget_error = budget_state(budget, brain)

    if budget_error and decision.action != "answer":
        state.emit(
            AgentStep(
                index,
                "budget",
                "Бюджет исчерпан",
                f"{budget_error} Потрачено: {tokens} токенов, "
                f"${cost:.4f}. Задача остановлена.",
            )
        )

        return AgentResult(
            steps=state.steps,
            error=f"{budget_error} Потрачено {tokens} токенов "
            f"(${cost:.4f}). Задача остановлена.",
            context_chars=state.context_peak,
        )

    return decision, assistant_raw


def _finish(
    state: _RunState,
    *,
    task: str,
    brain: Brain,
    native: bool,
    chat_mode: bool,
    max_prompt_chars: int,
    max_steps: int,
) -> AgentResult:
    """Просит итог без инструментов или сообщает о лимите."""

    prompt_builder = build_native_prompt if native else build_prompt

    # Шаги кончились: просим итог без инструментов, чтобы пользователь
    # получил ответ, а не только «достигнут лимит».
    summarize = getattr(brain, "summarize", None)

    if chat_mode and callable(getattr(brain, "finish_chat", None)):
        try:
            text = str(brain.finish_chat(state.chat) or "").strip()
        except Exception as error:  # noqa: BLE001 — покажем в трейсе
            text = ""
            state.emit(
                AgentStep(
                    state.position,
                    "error",
                    "Итог не получен",
                    f"{type(error).__name__}: {error}",
                )
            )

        if text:
            state.emit(
                AgentStep(state.position, "answer", "Ответ по итогам", text[:500])
            )

            return AgentResult(
                steps=state.steps,
                answer=text,
                context_chars=state.context_peak,
            )

    if callable(summarize) and state.history and not chat_mode:
        final_prompt = prompt_builder(
            task,
            state.history,
            max_chars=max_prompt_chars,
            final_note=(
                "Шаги закончились, инструменты недоступны. Дай короткий "
                "ответ по тому, что уже известно, и честно перечисли, "
                "чего не хватило."
            ),
        )

        try:
            text = str(summarize(final_prompt) or "").strip()
        except Exception as error:  # noqa: BLE001 — покажем в трейсе
            text = ""
            state.emit(
                AgentStep(
                    state.position,
                    "error",
                    "Итог не получен",
                    f"{type(error).__name__}: {error}",
                )
            )

        if text:
            state.emit(
                AgentStep(
                    state.position,
                    "answer",
                    "Ответ по итогам",
                    text[:500],
                )
            )

            return AgentResult(
                steps=state.steps,
                answer=text,
                context_chars=state.context_peak,
            )

    return AgentResult(
        steps=state.steps,
        error=f"Достигнут лимит шагов: {max_steps}.",
        context_chars=state.context_peak,
    )

