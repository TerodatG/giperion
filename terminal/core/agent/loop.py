# Giperion/terminal/core/agent/loop.py                              v001
# Цикл агента: решение модели → инструмент → наблюдение → ответ.
# Последнее изменение: первый вариант — только чтение, лимит шагов.

import json
import re
from pathlib import Path
from typing import Callable, Protocol

from terminal.core.agent import registry
from terminal.core.agent.context import (
    DATA_CLOSE,
    DATA_OPEN,
    MAX_PROMPT,
    DecisionError,
    build_native_prompt,
    build_prompt,
    is_within_budget,
    parse_decision,
)
from terminal.core.agent.guard import find_instructions, mark_untrusted
from terminal.core.agent.protocol import (
    AgentDecision,
    AgentResult,
    AgentStep,
    ApprovalRequest,
    ApprovalResult,
    ToolCall,
    ToolResult,
)
from terminal.core.agent.redact import redact

DEFAULT_MAX_STEPS = 8

PATH_TOKEN = re.compile(
    r"[\w./\\-]+\.(?:py|md|json|jsonc|ui|txt|toml|cfg|ini|"
    r"ps1|bat|cmd|yml|yaml|html|css|js|ts|csv)\b",
    re.IGNORECASE,
)

QUOTED = re.compile(
    r"«([^»]{3,80})»|\"([^\"]{3,80})\"|`([^`]{3,80})`"
)


def grounding_calls(task: str, root: Path) -> list[ToolCall]:
    """Первый шаг без модели: дать ей реальные факты о проекте.

    Гадательных поисковых запросов здесь нет: если в задаче назван
    файл — читаем его, иначе показываем корень и, при явной цитате,
    выполняем точный поиск.
    """

    match = PATH_TOKEN.search(task)

    if match:
        path = match.group(0).strip(" .,:;()[]\"'")

        if path and (root / path).exists():
            return [ToolCall(tool="read_file", args={"path": path})]

    calls = [ToolCall(tool="list_dir", args={"path": "."})]

    quoted = QUOTED.search(task)

    if quoted:
        query = next(
            (group for group in quoted.groups() if group),
            "",
        ).strip()

        if query:
            calls.append(
                ToolCall(tool="search_text", args={"query": query})
            )

    return calls


class Brain(Protocol):
    """Источник решений агента: модель или сценарий в тестах."""

    def decide(self, prompt: str) -> str | AgentDecision:
        """Возвращает JSON-решение или готовое решение агента."""


def _approval_title(call: ToolCall) -> str:
    """Заголовок подтверждения по типу действия."""

    titles = {
        "run_tests": "Запустить тесты",
        "run_command": "Выполнить команду",
        "git_commit": "Коммит",
        "git_restore": "Откатить файл",
    }

    return titles.get(call.tool, "Изменить файл")


def _call_title(call: ToolCall) -> str:
    """Короткая подпись вызова для трейса."""

    args = json.dumps(call.args, ensure_ascii=False)

    return f"{call.tool}({args})"


def _call_detail(result: ToolResult) -> str:
    """Первая строка результата для трейса."""

    text = str(result.text or "").strip()
    first = text.splitlines()[0] if text else ""

    if result.ok:
        return first[:300]

    return "ошибка: " + first[:300]


WRITE_TOOLS = {"apply_patch", "write_file", "git_restore"}

# Что можно разрешить до конца задачи одним нажатием. Коммит и откат
# остаются отдельными решениями: они меняют историю репозитория.
REMEMBERABLE = {"apply_patch", "write_file", "run_tests", "run_command"}


def approval_key(call: ToolCall) -> str:
    """Стабильный ключ действия для «не спрашивать до конца задачи»."""

    if call.tool not in REMEMBERABLE:
        return ""

    if call.tool in ("apply_patch", "write_file"):
        path = str(call.args.get("path") or "").strip()

        return "file:" + path if path else ""

    if call.tool == "run_command":
        command = str(call.args.get("command") or "").strip()

        return "command:" + command if command else ""

    return call.tool


def _repeated_call(
    history: list[tuple[ToolCall, ToolResult]],
    call: ToolCall,
    window: int = 2,
) -> ToolCall | None:
    """Ищет такой же вызов недавно, если после него не было записи.

    Повторять чтение после правки можно: файл мог измениться. Повторять
    его подряд, ничего не сделав, — бесполезный шаг.
    """

    recent = history[-window:]

    for offset in range(len(recent) - 1, -1, -1):
        previous, result = recent[offset]

        if previous.tool != call.tool or previous.args != call.args:
            continue

        if not result.ok:
            return None

        after = recent[offset + 1:]

        if any(item[0].tool in WRITE_TOOLS for item in after):
            return None

        return previous

    return None


def _usage(brain: "Brain") -> tuple[int, float]:
    """Сколько токенов и денег потратил мозг, если он это умеет."""

    tokens = getattr(brain, "total_tokens", 0)
    cost = getattr(brain, "cost", 0.0)

    try:
        tokens = int(tokens)
    except (TypeError, ValueError):
        tokens = 0

    try:
        cost = float(cost)
    except (TypeError, ValueError):
        cost = 0.0

    return max(0, tokens), max(0.0, cost)


def budget_state(budget, brain: "Brain") -> tuple[int, float, str]:
    """Токены, стоимость и причина остановки (или пустая строка)."""

    from terminal.core.agent.budget import exceeded

    tokens, cost = _usage(brain)

    if budget is None or not getattr(budget, "enabled", False):
        return tokens, cost, ""

    return tokens, cost, exceeded(budget, tokens, cost)


PLAN_MARKS = {
    "done": "[x]",
    "doing": "[>]",
    "pending": "[ ]",
}


def render_plan(steps: list[dict]) -> str:
    """План в виде чек-листа для трейса и ответа модели."""

    lines = []

    for number, item in enumerate(steps, start=1):
        status = str(item.get("status") or "pending")
        mark = PLAN_MARKS.get(status, "[ ]")
        text = str(item.get("text") or "")

        lines.append(f"{number}. {mark} {text}")

    return "\n".join(lines)


def _observation_block(
    call: ToolCall,
    result: ToolResult,
    limit: int = 3000,
) -> str:
    """Наблюдение в виде блока данных для переписки."""

    text = str(result.text or "")

    if len(text) > limit:
        text = text[:limit] + "\n… обрезано"

    return f"{DATA_OPEN} {call.tool}>>>\n{text}\n{DATA_CLOSE}"


def _chat_chars(messages: list[dict]) -> int:
    """Грубая оценка размера переписки в символах."""

    total = 0

    for message in messages:
        total += len(str(message.get("content") or ""))
        total += len(json.dumps(message.get("tool_calls") or []))

    return total


def _trim_chat(messages: list[dict], max_chars: int) -> list[dict]:
    """Выбрасывает старые шаги, сохраняя систему, задачу и порядок ролей."""

    trimmed = list(messages)

    while len(trimmed) > 4 and _chat_chars(trimmed) > max_chars:
        del trimmed[2]

        while len(trimmed) > 2 and trimmed[2].get("role") == "tool":
            del trimmed[2]

    return trimmed


def _compact_chat(
    messages: list[dict],
    recent_steps: int = 2,
    limit: int = 900,
) -> None:
    """Сжимает давние результаты инструментов, не ломая пары ролей."""

    starts = [
        index
        for index, message in enumerate(messages)
        if message.get("role") == "assistant"
    ]

    if len(starts) <= recent_steps:
        return

    boundary = starts[-recent_steps]

    for index in range(2, boundary):
        message = messages[index]

        if message.get("role") != "tool":
            continue

        content = str(message.get("content") or "")

        if len(content) <= limit:
            continue

        messages[index] = {
            **message,
            "content": content[:limit] + "\n… старый результат сжат",
        }


def _append_chat_step(
    chat: list[dict],
    assistant: dict,
    entries: list[tuple[ToolCall, ToolResult]],
) -> None:
    """Добавляет в переписку ответ ассистента и результаты инструментов."""

    message = dict(assistant or {})
    message.setdefault("role", "assistant")
    message["content"] = message.get("content") or ""

    raw_calls = message.get("tool_calls") or []

    chat.append(message)

    for position, (call, result) in enumerate(entries):
        call_id = ""

        if position < len(raw_calls):
            call_id = str(
                (raw_calls[position] or {}).get("id") or ""
            )

        chat.append(
            {
                "role": "tool",
                "tool_call_id": call_id or f"call_{position}",
                "content": _observation_block(call, result, 4000),
            }
        )


def _run_subagent(
    call: ToolCall,
    brain: "Brain",
    root: Path,
    depth: int,
    allow_subagent: bool,
    should_stop: Callable[[], bool] | None,
) -> ToolResult:
    """Запускает читающего подагента без права записи."""

    if depth >= 1 or not allow_subagent:
        return ToolResult(
            False,
            "Подагенты не могут вызывать других подагентов.",
        )

    task = str(call.args.get("task") or "").strip()

    if not task:
        return ToolResult(False, "Подагенту не передана задача.")

    result = run_agent(
        task,
        brain,
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

    if result.answer:
        return ToolResult(True, result.answer)

    if result.cancelled:
        return ToolResult(False, "Подагент остановлен.")

    return ToolResult(False, result.error or "Подагент не ответил.")


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
) -> AgentResult:
    """Выполняет задачу по шагам и возвращает итог и трейс."""

    clean_task = str(task or "").strip()

    if not clean_task:
        return AgentResult(error="Пустая задача.")

    if policy not in ("read", "confirm", "trust"):
        policy = "confirm"

    steps: list[AgentStep] = []
    history: list[tuple[ToolCall, ToolResult]] = [
        (call, ToolResult(result.ok, redact(result.text).text))
        for call, result in (initial_history or [])
    ]
    context_peak = 0
    native = bool(getattr(brain, "native", False))
    position = 0
    # Разрешения «до конца задачи»: ключи действий, которые пользователь
    # больше не хочет подтверждать. Живут только в этом прогоне.
    remembered: set[str] = allowed if allowed is not None else set()

    def remember(call: ToolCall, result: ToolResult) -> None:
        # Секреты не попадают ни в промпт, ни в историю задачи, ни в
        # журнал: чистим наблюдение сразу, как только инструмент ответил.
        clean = redact(result.text)

        if clean.hidden:
            result = ToolResult(result.ok, clean.text)

            emit(
                AgentStep(
                    position,
                    "secret",
                    "Секреты скрыты",
                    f"скрыто фрагментов: {clean.hidden} · "
                    f"{call.tool}",
                )
            )

        # Инструкции внутри файлов — это данные, а не команды. Не
        # выбрасываем текст, но помечаем и предупреждаем в трейсе.
        flags = find_instructions(result.text)

        if flags:
            result = ToolResult(
                result.ok,
                mark_untrusted(result.text, flags),
            )

            emit(
                AgentStep(
                    position,
                    "security",
                    "Похоже на внедрение инструкций",
                    f"{call.tool}: " + ", ".join(flags[:5]),
                )
            )

        history.append((call, result))

        if on_history is not None:
            on_history(history)

    def emit(step: AgentStep) -> None:
        steps.append(step)

        if on_step is not None:
            on_step(step)

    def stopped() -> bool:
        return bool(should_stop and should_stop())

    if ground_first and not history:
        for call in grounding_calls(clean_task, root):
            result = registry.execute(root, call)

            emit(
                AgentStep(
                    0,
                    "tool",
                    "старт · " + _call_title(call),
                    _call_detail(result),
                )
            )

            remember(call, result)

    chat_mode = bool(
        getattr(brain, "messages_mode", False)
        and callable(getattr(brain, "decide_chat", None))
    )
    chat: list[dict] = []

    if chat_mode:
        chat = brain.begin(
            clean_task,
            [
                _observation_block(call, result)
                for call, result in history[-4:]
            ],
        )

    for index in range(1, max(max_steps, 1) + 1):
        position = index

        if stopped():
            return AgentResult(
                steps=steps,
                cancelled=True,
                context_chars=context_peak,
            )

        prompt_builder = build_native_prompt if native else build_prompt

        final_note = ""

        if index >= max(max_steps, 1):
            final_note = (
                "Это последний шаг, инструменты больше не выполняются. "
                "Дай ответ по тому, что уже есть в истории, и честно "
                "скажи, чего не хватило."
                if native
                else (
                    "Это последний шаг, инструменты больше не выполняются. "
                    'Верни {"action": "answer", "text": "..."} по тому, '
                    "что уже есть в истории."
                )
            )

        assistant_raw: dict = {}

        if chat_mode:
            _compact_chat(chat)
            context_peak = max(context_peak, _chat_chars(chat))

            if _chat_chars(chat) > max_prompt_chars:
                chat = _trim_chat(chat, max_prompt_chars)
                context_peak = max(context_peak, _chat_chars(chat))

            if _chat_chars(chat) > max_prompt_chars:
                return AgentResult(
                    steps=steps,
                    error=(
                        "Контекст превысил бюджет "
                        f"{max_prompt_chars} символов."
                    ),
                    context_chars=context_peak,
                )

            try:
                decision, assistant_raw = brain.decide_chat(chat)
            except Exception as error:  # noqa: BLE001 — покажем в трейсе
                emit(
                    AgentStep(
                        index,
                        "error",
                        "Модель не ответила",
                        f"{type(error).__name__}: {error}",
                    )
                )

                return AgentResult(
                    steps=steps,
                    error=f"Модель не ответила: {error}",
                    context_chars=context_peak,
                )
        else:
            prompt = prompt_builder(
                clean_task,
                history,
                max_chars=max_prompt_chars,
                final_note=final_note,
            )
            context_peak = max(context_peak, len(prompt))

            if not is_within_budget(prompt, max_prompt_chars):
                return AgentResult(
                    steps=steps,
                    error=(
                        "Контекст превысил бюджет "
                        f"{max_prompt_chars} символов."
                    ),
                    context_chars=context_peak,
                )

            try:
                raw = brain.decide(prompt)
            except Exception as error:  # noqa: BLE001 — покажем в трейсе
                emit(
                    AgentStep(
                        index,
                        "error",
                        "Модель не ответила",
                        f"{type(error).__name__}: {error}",
                    )
                )

                return AgentResult(
                    steps=steps,
                    error=f"Модель не ответила: {error}",
                    context_chars=context_peak,
                )

        if not chat_mode:
            try:
                decision = (
                    raw
                    if isinstance(raw, AgentDecision)
                    else parse_decision(raw)
                )
            except DecisionError as error:
                emit(
                    AgentStep(
                        index,
                        "error",
                        "Некорректное решение",
                        str(error),
                    )
                )

                remember(
                    ToolCall(tool="format", args={}),
                    ToolResult(
                        False,
                        "Ответ не разобрался: "
                        f"{error}. Верни только JSON по схеме.",
                    ),
                )

                continue

        tokens, cost, budget_error = budget_state(budget, brain)

        if budget_error and decision.action != "answer":
            emit(
                AgentStep(
                    index,
                    "budget",
                    "Бюджет исчерпан",
                    f"{budget_error} Потрачено: {tokens} токенов, "
                    f"${cost:.4f}. Задача остановлена.",
                )
            )

            return AgentResult(
                steps=steps,
                error=f"{budget_error} Потрачено {tokens} токенов "
                f"(${cost:.4f}). Задача остановлена.",
                context_chars=context_peak,
            )

        if decision.action == "answer":
            if require_tool_first and not history:
                emit(
                    AgentStep(
                        index,
                        "error",
                        "Нужен шаг чтения",
                        "Модель ответила, ничего не прочитав.",
                    )
                )
                remember(
                    ToolCall(tool="policy", args={}),
                    ToolResult(
                        False,
                        "Сначала вызови list_dir, read_file или "
                        "search_text, а потом отвечай.",
                    ),
                )

                continue

            emit(
                AgentStep(
                    index,
                    "answer",
                    "Ответ",
                    decision.text[:500],
                )
            )

            return AgentResult(
                answer=decision.text,
                steps=steps,
                context_chars=context_peak,
            )

        calls = list(decision.calls)

        if decision.call is not None:
            calls.append(decision.call)

        if not calls:
            continue

        step_start = len(history)

        for call in calls:
            repeated = _repeated_call(history, call)

            if repeated is not None:
                previous = next(
                    (
                        result
                        for call_item, result in reversed(history)
                        if call_item.tool == call.tool
                        and call_item.args == call.args
                    ),
                    None,
                )
                preview = str(previous.text if previous else "").strip()

                emit(
                    AgentStep(
                        index,
                        "error",
                        "Повтор вызова",
                        _call_title(call) + " — уже было, результат ниже.",
                    )
                )
                remember(
                    call,
                    ToolResult(
                        False,
                        "Этот вызов уже был. Не повторяй его, а используй "
                        "его результат:\n"
                        + (preview[:1500] or "(результат пуст)"),
                    ),
                )

                continue

            invalid = registry.validate_call(call)

            if invalid is not None:
                emit(
                    AgentStep(
                        index,
                        "error",
                        "Неверные аргументы",
                        invalid.text[:300],
                    )
                )
                remember(call, invalid)

                continue

            if call.tool == "update_plan":
                steps_raw = call.args.get("steps")

                if not isinstance(steps_raw, list) or not steps_raw:
                    remember(
                        call,
                        ToolResult(
                            False,
                            "План пуст: нужен непустой список шагов "
                            'со статусами "pending"/"doing"/"done".',
                        ),
                    )

                    continue

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
                    remember(
                        call,
                        ToolResult(
                            False,
                            "В плане нет ни одного пункта с текстом.",
                        ),
                    )

                    continue

                plan = normalized

                emit(
                    AgentStep(
                        index,
                        "plan",
                        f"План · {len(plan)} пунктов",
                        render_plan(plan),
                    )
                )
                remember(
                    call,
                    ToolResult(
                        True,
                        "План обновлён:\n" + render_plan(plan),
                    ),
                )

                continue

            if call.tool == "ask_subagent":
                result = _run_subagent(
                    call,
                    brain,
                    root,
                    depth,
                    allow_subagent,
                    should_stop,
                )

                emit(
                    AgentStep(
                        index,
                        "subagent",
                        "Подагент",
                        result.text[:500],
                    )
                )

                remember(call, result)

                continue

            spec = registry.get_spec(call.tool)
            risk = spec.risk if spec is not None else "read"
            requires_approval = registry.needs_approval(call)

            if requires_approval and policy == "read":
                emit(
                    AgentStep(
                        index,
                        "approval",
                        "Запрещено политикой · "
                        + _approval_title(call),
                        "Политика «только чтение».",
                    )
                )
                remember(
                    call,
                    ToolResult(
                        False,
                        "Политика «только чтение»: действие "
                        "запрещено. Предложи ответ без изменений.",
                    ),
                )

                continue

            if (
                requires_approval
                and policy == "trust"
                and risk == "write"
                and call.tool != "git_commit"
            ):
                emit(
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

            if requires_approval and key and key in remembered:
                emit(
                    AgentStep(
                        index,
                        "approval",
                        "Без вопроса · " + _approval_title(call),
                        "Разрешено до конца задачи: " + key,
                    )
                )
                requires_approval = False

            if requires_approval:
                preview = registry.preview(root, call)

                if not preview.ok:
                    emit(
                        AgentStep(
                            index,
                            "error",
                            "Действие невозможно",
                            preview.text[:300],
                        )
                    )
                    remember(call, preview)

                    continue

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

                emit(
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
                    if key not in remembered:
                        remembered.add(key)

                    emit(
                        AgentStep(
                            index,
                            "approval",
                            "Разрешено до конца задачи · "
                            + _approval_title(call),
                            key,
                        )
                    )

                if not approved:
                    remember(
                        call,
                        ToolResult(
                            False,
                            "Пользователь отклонил действие. "
                            "Предложи другой путь или ответь.",
                        ),
                    )

                    continue

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

            result = registry.execute(root, call)

            emit(
                AgentStep(
                    index,
                    "tool",
                    _call_title(call),
                    _call_detail(result),
                )
            )

            remember(call, result)

        if chat_mode:
            _append_chat_step(
                chat,
                assistant_raw,
                history[step_start:],
            )

    # Шаги кончились: просим итог без инструментов, чтобы пользователь
    # получил ответ, а не только «достигнут лимит».
    summarize = getattr(brain, "summarize", None)

    if chat_mode and callable(getattr(brain, "finish_chat", None)):
        try:
            text = str(brain.finish_chat(chat) or "").strip()
        except Exception as error:  # noqa: BLE001 — покажем в трейсе
            text = ""
            emit(
                AgentStep(
                    index,
                    "error",
                    "Итог не получен",
                    f"{type(error).__name__}: {error}",
                )
            )

        if text:
            emit(
                AgentStep(index, "answer", "Ответ по итогам", text[:500])
            )

            return AgentResult(
                steps=steps,
                answer=text,
                context_chars=context_peak,
            )

    if callable(summarize) and history and not chat_mode:
        final_prompt = prompt_builder(
            clean_task,
            history,
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
            emit(
                AgentStep(
                    index,
                    "error",
                    "Итог не получен",
                    f"{type(error).__name__}: {error}",
                )
            )

        if text:
            emit(
                AgentStep(
                    index,
                    "answer",
                    "Ответ по итогам",
                    text[:500],
                )
            )

            return AgentResult(
                steps=steps,
                answer=text,
                context_chars=context_peak,
            )

    return AgentResult(
        steps=steps,
        error=f"Достигнут лимит шагов: {max_steps}.",
        context_chars=context_peak,
    )
