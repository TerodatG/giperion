# Giperion/terminal/core/agent/loop_phases.py                         v001
# Фазы прогона: состояние, старт, решение, отказ и итог.
# Последнее изменение: вынесено из loop.


from terminal.core.agent.budget import warning as budget_warning
from terminal.core.agent.context import (
    DecisionError,
    build_native_prompt,
    build_prompt,
    is_within_budget,
    parse_decision,
)
from terminal.core.agent.loop_helpers import (
    Brain,
    StepTimeout,
    _chat_chars,
    _compact_chat,
    _trim_chat,
    budget_state,
    call_with_timeout,
)
from terminal.core.agent.loop_state import (
    READ_TOOLS,  # noqa: F401 — реэкспорт для тестов
    _create_state,  # noqa: F401 — реэкспорт для loop
    _prepare_run,  # noqa: F401 — реэкспорт для loop
    _RunState,  # noqa: F401 — реэкспорт для тестов
)
from terminal.core.agent.protocol import (
    AgentDecision,
    AgentResult,
    AgentStep,
    ToolCall,
    ToolResult,
)


def _step_note(index: int, max_steps: int, native: bool) -> str:
    """Подсказка модели на последний шаг."""

    if index < max(max_steps, 1):
        return ""

    if native:
        return (
            "Это последний шаг. Если вызовешь инструмент, он ещё "
            "выполнится, но следующего решения уже не будет — затем "
            "я попрошу итог. Лучше ответь по тому, что уже есть, и "
            "честно скажи, чего не хватило."
        )

    return (
        "Это последний шаг. Если вернёшь вызов инструмента, он ещё "
        "выполнится, но следующего шага уже не будет — затем я "
        "попрошу итог. Лучше верни "
        '{"action": "answer", "text": "..."} по тому, что уже есть.'
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

    if not require_tool_first or state.read_ok:
        return False

    # Псевдо-вызов policy нужен только как наблюдение для модели.
    # Он не должен считаться настоящей попыткой что-то сделать.
    if any(
        call.tool != "policy"
        for call, _result in state.history
    ):
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


def _context_error(state: "_RunState", max_chars: int) -> AgentResult:
    """Ошибка превышения бюджета контекста."""

    return AgentResult(
        steps=state.steps,
        error=f"Контекст превысил бюджет {max_chars} символов.",
        context_chars=state.context_peak,
    )


def _model_error(
    state: "_RunState",
    index: int,
    error: Exception,
    timed_out: bool,
) -> AgentResult:
    """Ошибка модели: таймаут шага или отказ провайдера."""

    if timed_out:
        title = "Таймаут шага"
        detail = str(error)
        text = str(error)
    else:
        title = "Модель не ответила"
        detail = f"{type(error).__name__}: {error}"
        text = f"Модель не ответила: {error}"

    state.emit(AgentStep(index, "error", title, detail))

    return AgentResult(
        steps=state.steps,
        error=text,
        context_chars=state.context_peak,
    )


def _decide_chat(
    state: "_RunState",
    index: int,
    brain: Brain,
    max_prompt_chars: int,
    step_timeout: float,
) -> AgentResult | tuple[AgentDecision, dict]:
    """Шаг в режиме переписки."""

    _compact_chat(state.chat)
    state.context_peak = max(state.context_peak, _chat_chars(state.chat))

    if _chat_chars(state.chat) > max_prompt_chars:
        state.chat = _trim_chat(state.chat, max_prompt_chars)
        state.context_peak = max(state.context_peak, _chat_chars(state.chat))

    if _chat_chars(state.chat) > max_prompt_chars:
        return _context_error(state, max_prompt_chars)

    try:
        return call_with_timeout(
            lambda: brain.decide_chat(state.chat),
            step_timeout,
        )
    except StepTimeout as error:
        return _model_error(state, index, error, True)
    except Exception as error:  # noqa: BLE001 — покажем в трейсе
        return _model_error(state, index, error, False)


def _decide_prompt(
    state: "_RunState",
    index: int,
    brain: Brain,
    *,
    task: str,
    native: bool,
    max_prompt_chars: int,
    final_note: str,
    step_timeout: float,
) -> AgentResult | object:
    """Шаг с одним текстовым промптом."""

    builder = build_native_prompt if native else build_prompt
    prompt = builder(
        task,
        state.history,
        max_chars=max_prompt_chars,
        final_note=final_note,
        root=state.root,
    )
    state.context_peak = max(state.context_peak, len(prompt))

    if not is_within_budget(prompt, max_prompt_chars):
        return _context_error(state, max_prompt_chars)

    try:
        return call_with_timeout(
            lambda: brain.decide(prompt),
            step_timeout,
        )
    except StepTimeout as error:
        return _model_error(state, index, error, True)
    except Exception as error:  # noqa: BLE001 — покажем в трейсе
        return _model_error(state, index, error, False)


def _decide(
    state: "_RunState",
    index: int,
    *,
    task: str,
    brain: Brain,
    native: bool,
    chat_mode: bool,
    max_prompt_chars: int,
    final_note: str,
    budget,
    step_timeout: float = 180.0,
) -> AgentResult | tuple[AgentDecision, dict] | None:
    """Спрашивает модель и проверяет бюджет шага."""

    assistant_raw: dict = {}

    if chat_mode:
        outcome = _decide_chat(
            state,
            index,
            brain,
            max_prompt_chars,
            step_timeout,
        )

        if isinstance(outcome, AgentResult):
            return outcome

        decision, assistant_raw = outcome
    else:
        raw = _decide_prompt(
            state,
            index,
            brain,
            task=task,
            native=native,
            max_prompt_chars=max_prompt_chars,
            final_note=final_note,
            step_timeout=step_timeout,
        )

        if isinstance(raw, AgentResult):
            return raw

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

    near = (
        budget_warning(budget, tokens, cost)
        if budget is not None
        else ""
    )

    if near and not state.budget_warned:
        state.budget_warned = True
        state.emit(
            AgentStep(
                index,
                "budget",
                "Бюджет почти исчерпан",
                near + " Следующий шаг может остановить задачу.",
            )
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
    budget=None,
) -> AgentResult:
    """Просит итог без инструментов или сообщает о лимите."""

    prompt_builder = build_native_prompt if native else build_prompt

    if budget is not None and getattr(budget, "enabled", False):
        tokens, cost, reason = budget_state(budget, brain)

        if reason:
            state.emit(
                AgentStep(
                    state.position,
                    "budget",
                    "Бюджет исчерпан",
                    f"{reason} Дополнительный итог не запрошен.",
                )
            )

            return AgentResult(
                steps=state.steps,
                error=(
                    f"{reason} Потрачено {tokens} токенов "
                    f"(${cost:.4f}). Итог не запрошен."
                ),
                context_chars=state.context_peak,
            )

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
            root=state.root,
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

