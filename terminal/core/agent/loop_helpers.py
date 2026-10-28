# Giperion/terminal/core/agent/loop_helpers.py                        v001
# Помощники цикла: заземление, подписи, ключи, бюджет и chat-история.
# Последнее изменение: вынесено из loop.

import json
import re
from pathlib import Path
from typing import Protocol

from terminal.core.agent.context import DATA_CLOSE, DATA_OPEN
from terminal.core.agent.protocol import (
    AgentDecision,
    ToolCall,
    ToolResult,
)

DEFAULT_MAX_STEPS = 8

PATH_TOKEN = re.compile(
    r"[\w./\\-]+\.(?:py|md|json|jsonc|ui|txt|toml|cfg|ini|"
    r"ps1|bat|cmd|yml|yaml|html|css|js|ts|csv)\b",
    re.IGNORECASE,
)

QUOTED = re.compile(
    r"«([^»]{3,80})»|\"([^\"]{3,80})\"|`([^`]{3,80})`"
)

QUESTION_RE = re.compile(
    r"\b(где|найди|как|почему|зачем|какие|какой|какая|кто|когда|"
    r"откуда|что|чем|сколько|which|where|why|how|what|find|search)\b",
    re.IGNORECASE,
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

    if (
        QUESTION_RE.search(task)
        and len(task.split()) >= 4
    ):
        from terminal.core.agent import settings

        if settings.semantic_enabled():
            calls.append(
                ToolCall(
                    tool="find_relevant",
                    args={"query": task[:400], "limit": 5},
                )
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
        "fetch_url": "Открыть страницу",
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
REMEMBERABLE = {
    "apply_patch",
    "write_file",
    "run_tests",
    "run_command",
    "fetch_url",
    "browser_read",
    "browser_act",
}


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

    if call.tool in ("fetch_url", "browser_read", "browser_act"):
        from terminal.core.agent import web

        host = web.host_of(str(call.args.get("url") or ""))

        return "web:" + host if host else ""

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


def _smart_excerpt(text: str, limit: int) -> str:
    """Сжимает вывод, сохраняя ошибки, пути и решения."""

    marker = "\n… старый результат сжат"
    budget = max(100, int(limit) - len(marker))
    value = str(text or "")

    if len(value) <= budget:
        return value

    lines = value.splitlines()
    head = lines[:3]
    used = sum(len(line) + 1 for line in head)
    scored: list[tuple[int, int, str]] = []

    for index, line in enumerate(lines[3:], start=3):
        lowered = line.casefold()
        score = 0

        if any(
            word in lowered
            for word in (
                "error",
                "ошиб",
                "exception",
                "traceback",
                "failed",
                "не найден",
                "запрещ",
            )
        ):
            score += 5

        if PATH_TOKEN.search(line):
            score += 4

        if any(
            word in lowered
            for word in (
                "решен",
                "выбрал",
                "нужно",
                "нельзя",
                "итог",
                "важно",
            )
        ):
            score += 3

        if any(char.isdigit() for char in line):
            score += 1

        if score:
            scored.append((score, index, line))

    chosen: set[int] = set(range(len(head)))

    for _score, index, line in sorted(
        scored,
        key=lambda item: (-item[0], item[1]),
    ):
        if used + len(line) + 1 > budget:
            continue

        chosen.add(index)
        used += len(line) + 1

    if len(chosen) == len(head):
        return value[:budget].rstrip() + marker

    result = "\n".join(
        line
        for index, line in enumerate(lines)
        if index in chosen
    )

    return result[:budget].rstrip() + marker


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
            "content": _smart_excerpt(content, limit),
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


class StepTimeout(RuntimeError):
    """Модель не уложилась в отведённое на шаг время."""


def call_with_timeout(func, timeout: float):
    """Выполняет вызов в отдельном потоке с ограничением ожидания.

    Прервать уже начатый HTTP-запрос нельзя, поэтому поток продолжает
    жить до ответа сервера, но цикл больше его не ждёт и задачу
    останавливает.
    """

    if not timeout or float(timeout) <= 0:
        return func()

    from concurrent.futures import (
        ThreadPoolExecutor,
    )
    from concurrent.futures import (
        TimeoutError as FutureTimeout,
    )

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(func)

    try:
        return future.result(timeout=float(timeout))
    except FutureTimeout as error:
        future.cancel()

        raise StepTimeout(
            f"Модель не ответила за {float(timeout):g} с."
        ) from error
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
