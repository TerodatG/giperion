# Giperion/terminal/core/agent/loop_tools.py                          v001
# Выполнение вызовов: проверки, план, подагенты и подтверждения.
# Последнее изменение: вынесено из loop.

from pathlib import Path
from typing import Callable

from terminal.core.agent import registry
from terminal.core.agent.loop_helpers import (
    Brain,
    _approval_title,
    _call_detail,
    _call_title,
    _repeated_call,
    approval_key,
    render_plan,
)
from terminal.core.agent.loop_phases import _RunState
from terminal.core.agent.protocol import (
    AgentStep,
    ApprovalRequest,
    ApprovalResult,
    ToolCall,
    ToolResult,
)


def _skip_bad_call(
    state: _RunState,
    index: int,
    call: ToolCall,
) -> bool:
    """Отсекает повтор и неверные аргументы; True — вызов обработан."""

    repeated = _repeated_call(state.history, call)

    if repeated is not None:
        previous = next(
            (
                result
                for call_item, result in reversed(state.history)
                if call_item.tool == call.tool
                and call_item.args == call.args
            ),
            None,
        )
        preview = str(previous.text if previous else "").strip()

        state.emit(
            AgentStep(
                index,
                "error",
                "Повтор вызова",
                _call_title(call) + " — уже было, результат ниже.",
            )
        )
        state.remember(
            call,
            ToolResult(
                False,
                "Этот вызов уже был. Не повторяй его, а используй "
                "его результат:\n"
                + (preview[:1500] or "(результат пуст)"),
            ),
        )

        return True

    invalid = registry.validate_call(call)

    if invalid is not None:
        state.emit(
            AgentStep(
                index,
                "error",
                "Неверные аргументы",
                invalid.text[:300],
            )
        )
        state.remember(call, invalid)

        return True

    return False


def _run_plan_call(
    state: _RunState,
    index: int,
    call: ToolCall,
) -> bool:
    """Обновляет чек-лист; True — вызов был планом."""

    if call.tool != "update_plan":
        return False

    if call.tool == "update_plan":
        steps_raw = call.args.get("steps")

        if not isinstance(steps_raw, list) or not steps_raw:
            state.remember(
                call,
                ToolResult(
                    False,
                    "План пуст: нужен непустой список шагов "
                    'со статусами "pending"/"doing"/"done".',
                ),
            )

            return True

        normalized = []

        for item in steps_raw[:12]:
            if not isinstance(item, dict):
                continue

            text = str(item.get("text") or "").strip()
            status = str(item.get("status") or "pending").strip()

            if not text:
                continue

            if status not in ("pending", "doing", "done"):
                status = "pending"

            normalized.append(
                {"text": text[:200], "status": status}
            )

        if not normalized:
            state.remember(
                call,
                ToolResult(
                    False,
                    "В плане нет ни одного пункта с текстом.",
                ),
            )

            return True

        plan = normalized

        state.emit(
            AgentStep(
                index,
                "plan",
                f"План · {len(plan)} пунктов",
                render_plan(plan),
            )
        )
        state.remember(
            call,
            ToolResult(
                True,
                "План обновлён:\n" + render_plan(plan),
            ),
        )

        return True

    return False


def _run_subagent_call(
    state: _RunState,
    index: int,
    call: ToolCall,
    *,
    brain: Brain,
    root: Path,
    depth: int,
    allow_subagent: bool,
    should_stop: Callable[[], bool] | None,
    subagent_runner: Callable,
    subagent_tasks: Callable[[ToolCall], list[str]],
) -> bool:
    """Запускает подагента; True — вызов был подагентом."""

    if call.tool != "ask_subagent":
        return False

    if call.tool == "ask_subagent":
        result = subagent_runner(
            call,
            brain,
            root,
            depth,
            allow_subagent,
            should_stop,
        )

        count = len(subagent_tasks(call))

        state.emit(
            AgentStep(
                index,
                "subagent",
                (
                    f"Подагенты · {count}"
                    if count > 1
                    else "Подагент"
                ),
                result.text[:500],
            )
        )

        state.remember(call, result)

        return True

    return False


def _request_approval(
    state: _RunState,
    index: int,
    call: ToolCall,
    *,
    root: Path,
    key: str,
    approve: Callable[[ApprovalRequest], bool | ApprovalResult]
    | None,
) -> ToolCall | None:
    """Спрашивает подтверждение; None — действие отклонено."""

    preview = registry.preview(root, call)

    if not preview.ok:
        state.emit(
            AgentStep(
                index,
                "error",
                "Действие невозможно",
                preview.text[:300],
            )
        )
        state.remember(call, preview)

        return None

    payload_path, payload_old, payload_text = (
        registry.approval_payload(root, call)
    )

    request = ApprovalRequest(
        kind=call.tool,
        title=_approval_title(call),
        detail=preview.text,
        path=payload_path,
        new_text=payload_text,
        old_text=payload_old,
        key=key,
    )

    answer = approve(request) if approve else None

    if isinstance(answer, ApprovalResult):
        approved = bool(answer.approved)
        edited = answer.text
        keep = bool(answer.remember)
    else:
        approved = bool(answer)
        edited = None
        keep = False

    state.emit(
        AgentStep(
            index,
            "approval",
            (
                "Одобрено · "
                if approved
                else "Отклонено · "
            )
            + _approval_title(call),
            preview.text[:300],
        )
    )

    if approved and keep and key:
        if key not in state.remembered:
            state.remembered.add(key)

        state.emit(
            AgentStep(
                index,
                "approval",
                "Разрешено до конца задачи · "
                + _approval_title(call),
                key,
            )
        )

    if not approved:
        state.remember(
            call,
            ToolResult(
                False,
                "Пользователь отклонил действие. "
                "Предложи другой путь или ответь.",
            ),
        )

        return None

    if (
        edited is not None
        and payload_path
        and call.tool in ("write_file", "apply_patch")
    ):
        call = ToolCall(
            tool="write_file",
            args={
                "path": payload_path,
                "content": edited,
            },
        )
    return call


def _approve_and_execute(
    state: _RunState,
    index: int,
    call: ToolCall,
    *,
    root: Path,
    policy: str,
    approve: Callable[[ApprovalRequest], bool | ApprovalResult]
    | None,
) -> None:
    """Проверяет политику, спрашивает подтверждение и выполняет."""

    spec = registry.get_spec(call.tool)
    risk = spec.risk if spec is not None else "read"
    requires_approval = registry.needs_approval(call)

    if requires_approval and policy == "read":
        state.emit(
            AgentStep(
                index,
                "approval",
                "Запрещено политикой · "
                + _approval_title(call),
                "Политика «только чтение».",
            )
        )
        state.remember(
            call,
            ToolResult(
                False,
                "Политика «только чтение»: действие "
                "запрещено. Предложи ответ без изменений.",
            ),
        )

        return None

    if (
        requires_approval
        and policy == "trust"
        and risk == "write"
        and call.tool != "git_commit"
    ):
        state.emit(
            AgentStep(
                index,
                "approval",
                "Разрешено политикой · "
                + _approval_title(call),
                "Правки разрешены на время задачи.",
            )
        )
        requires_approval = False

    key = approval_key(call)

    if requires_approval and key and key in state.remembered:
        state.emit(
            AgentStep(
                index,
                "approval",
                "Без вопроса · " + _approval_title(call),
                "Разрешено до конца задачи: " + key,
            )
        )
        requires_approval = False

    if requires_approval:
        call = _request_approval(
            state,
            index,
            call,
            root=root,
            key=key,
            approve=approve,
        )

        if call is None:
            return None

    result = registry.execute(root, call)

    state.emit(
        AgentStep(
            index,
            "tool",
            _call_title(call),
            _call_detail(result),
        )
    )

    state.remember(call, result)


def _execute_calls(
    state: _RunState,
    index: int,
    calls: list[ToolCall],
    *,
    brain: Brain,
    root: Path,
    policy: str,
    approve: Callable[[ApprovalRequest], bool | ApprovalResult]
    | None,
    depth: int,
    allow_subagent: bool,
    should_stop: Callable[[], bool] | None,
    subagent_runner: Callable,
    subagent_tasks: Callable[[ToolCall], list[str]],
) -> None:
    """Выполняет вызовы одного шага: проверки, подтверждения и запись."""

    for call in calls:
        if _skip_bad_call(state, index, call):
            continue

        if _run_plan_call(state, index, call):
            continue

        if _run_subagent_call(
            state,
            index,
            call,
            brain=brain,
            root=root,
            depth=depth,
            allow_subagent=allow_subagent,
            should_stop=should_stop,
            subagent_runner=subagent_runner,
            subagent_tasks=subagent_tasks,
        ):
            continue

        _approve_and_execute(
            state,
            index,
            call,
            root=root,
            policy=policy,
            approve=approve,
        )

