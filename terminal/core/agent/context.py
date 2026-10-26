# Giperion/terminal/core/agent/context.py                           v001
# Сборка промпта агента и разбор его JSON-решения.
# Последнее изменение: первый вариант — строгий JSON без function calling.

import json

from terminal.core.agent.prompts import (
    DATA_RULE,
    NATIVE_SYSTEM_PROMPT,
)
from terminal.core.agent.protocol import (
    AgentDecision,
    ToolCall,
    ToolResult,
)
from terminal.core.agent.redact import redact
from terminal.core.agent.registry import tools_prompt

MAX_OBSERVATION = 4000
MAX_HISTORY = 24000
MAX_PROMPT = 60000
RECENT_STEPS = 3
SUMMARY_CHARS = 220

DATA_OPEN = "<<<ДАННЫЕ"
DATA_CLOSE = "<<<КОНЕЦ ДАННЫХ>>>"

SYSTEM_PROMPT = (
    "Ты — агент «Терминал» в проекте Giperion. Ты умеешь читать файлы, "
    "точечно менять их и запускать тесты. Любая запись и запуск тестов "
    "выполняются только после подтверждения пользователя.\n\n"
    "Отвечай ОДНИМ JSON-объектом и больше ничем:\n"
    '{"action": "tool", "tool": "read_file", "args": {"path": "README.md"}}\n'
    '{"action": "tool", "tool": "apply_patch", "args": {"path": "a.py", '
    '"old": "старый текст", "new": "новый текст"}}\n'
    '{"action": "tools", "calls": [{"tool": "read_file", "args": '
    '{"path": "a.py"}}, {"tool": "read_file", "args": {"path": "b.py"}}]}\n'
    '{"action": "answer", "text": "короткий ответ по-русски"}\n\n'
    "Правила:\n"
    "- не выдумывай содержимое файлов: сначала прочитай или найди;\n"
    "- нельзя отвечать, что ты «прочитал файл», если не было вызова "
    "read_file;\n"
    "- если задача про проект, первый шаг — инструмент, а не ответ;\n"
    "- функцию или класс ищи через find_symbol, текст — через "
    "search_text;\n"
    "- если точных слов не знаешь, ищи по смыслу через find_relevant;\n"
    "- большой файл читай частями: read_file(start, limit);\n"
    "- если задача требует больше двух шагов, сначала вызови "
    "update_plan и обновляй статусы пунктов по ходу;\n"
    "- для внешней документации используй fetch_url, если веб разрешён;\n"
    "- перед правкой прочитай файл и меняй точечно через apply_patch;\n"
    "- не переписывай файл целиком, если хватает замены фрагмента;\n"
    "- после правки запусти run_tests и посмотри на результат;\n"
    "- если тесты упали — прочитай ошибку, исправь и запусти снова;\n"
    "- для состояния репозитория используй git_status и git_diff;\n"
    "- коммить только изменённые файлы (paths) и только после успешных "
    "тестов;\n"
    "- откат файла — git_restore, если правка его сломала;\n"
    "- run_command — только для разрешённых команд из описания;\n"
    "- ask_subagent — поручить чтение подзадачи помощнику, он не пишет;\n"
    "- не трогай файлы, не относящиеся к задаче;\n"
    "- если действие отклонили, не повторяй его, предложи другой путь;\n"
    "- путь всегда относительный, внутри проекта;\n"
    "- в answer ссылайся на прочитанные файлы и результат тестов;\n"
    "- без markdown, без пояснений вокруг JSON.\n\n"
    + DATA_RULE
)


class DecisionError(Exception):
    """Ответ модели не разобрался как решение агента."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _shorten(text: str, limit: int) -> str:
    """Обрезает длинный текст для истории шагов."""

    clean = str(text).strip()

    if len(clean) <= limit:
        return clean

    return clean[:limit] + "\n… обрезано"



def _step_line(
    number: int,
    call: ToolCall,
    result: ToolResult,
    detail_limit: int,
) -> str:
    """Одна строка истории шага."""

    args = json.dumps(call.args, ensure_ascii=False)
    detail = _shorten(result.text, detail_limit)

    return (
        f"{number}. {call.tool}({args})\n"
        f"{DATA_OPEN} {call.tool}>>>\n"
        f"{detail}\n"
        f"{DATA_CLOSE}"
    )


LIMIT_LADDER = ((1200, 4000), (600, 1500), (300, 700), (150, 400))
HARD_LIMIT = 300


def _compose(
    task: str,
    history: list[tuple[ToolCall, ToolResult]],
    system: str,
    tools_block: str,
    next_line: str,
    final_note: str,
    other_limit: int,
    last_limit: int,
    old_budget: int,
) -> str:
    """Один вариант промпта с заданными лимитами на историю."""

    parts = [system]

    if tools_block:
        parts.append(tools_block)

    parts.append(f"Задача: {task.strip()}")

    if not history:
        parts.append("Выполненных шагов пока нет.")
    else:
        recent_start = max(0, len(history) - RECENT_STEPS)
        old_steps = history[:recent_start]

        if old_steps:
            summaries = [
                f"{number}. {call.tool}: "
                + _shorten(result.text, SUMMARY_CHARS).splitlines()[0]
                for number, (call, result) in enumerate(
                    old_steps,
                    start=1,
                )
            ]
            old_block = "\n".join(summaries)

            if len(old_block) > old_budget:
                old_block = (
                    f"[{len(old_steps)} старых шагов сжаты, "
                    "чтобы уложиться в контекст]"
                )

            parts.append("Ранее:\n" + old_block)

        recent_lines = ["Последние шаги:"]

        for number, (call, result) in enumerate(
            history[recent_start:],
            start=recent_start + 1,
        ):
            # Последний шаг показываем щедрее: по нему модель решает,
            # что делать дальше, и обрезка ломает счёт и списки.
            limit = last_limit if number == len(history) else other_limit

            recent_lines.append(_step_line(number, call, result, limit))

        parts.append("\n".join(recent_lines))

    parts.append(next_line)

    if final_note:
        parts.append(final_note)

    return "\n\n".join(parts)


def _assemble(
    task: str,
    history: list[tuple[ToolCall, ToolResult]],
    system: str,
    tools_block: str,
    next_line: str,
    max_chars: int,
    final_note: str = "",
) -> str:
    """Собирает промпт и сжимает историю ровно настолько, насколько нужно."""

    old_budget = min(MAX_HISTORY // 2, max(400, max_chars // 3))

    for other_limit, last_limit in LIMIT_LADDER:
        prompt = _compose(
            task,
            history,
            system,
            tools_block,
            next_line,
            final_note,
            other_limit,
            last_limit,
            old_budget,
        )

        if len(prompt) <= max_chars:
            return prompt

    # Жёсткий бюджет: оставляем только последний шаг.
    if history:
        last_call, last_result = history[-1]
        parts = [
            system,
            f"Задача: {task.strip()}",
            f"[{len(history)} шагов сжаты из-за лимита контекста]",
            _step_line(len(history), last_call, last_result, HARD_LIMIT),
            next_line,
        ]

        if final_note:
            parts.append(final_note)

        return "\n\n".join(parts)

    return _compose(
        task,
        history,
        system,
        tools_block,
        next_line,
        final_note,
        HARD_LIMIT,
        HARD_LIMIT,
        old_budget,
    )


def build_prompt(
    task: str,
    history: list[tuple[ToolCall, ToolResult]],
    max_chars: int = MAX_PROMPT,
    final_note: str = "",
) -> str:
    """Промпт для моделей, отвечающих JSON-решением."""

    prompt = _assemble(
        task,
        history,
        SYSTEM_PROMPT,
        "Доступные инструменты:\n" + tools_prompt(),
        "Следующий шаг — один JSON-объект:",
        max_chars,
        final_note,
    )

    return redact(prompt).text


def build_native_prompt(
    task: str,
    history: list[tuple[ToolCall, ToolResult]],
    max_chars: int = MAX_PROMPT,
    final_note: str = "",
) -> str:
    """Промпт для моделей с настоящими tool calls: без JSON и без схем."""

    prompt = _assemble(
        task,
        history,
        NATIVE_SYSTEM_PROMPT,
        "",
        "Следующий шаг: вызови инструмент или дай ответ текстом.",
        max_chars,
        final_note,
    )

    return redact(prompt).text


def is_within_budget(prompt: str, max_chars: int) -> bool:
    """Помещается ли промпт в бюджет."""

    return len(prompt) <= max_chars


def _strip_fence(text: str) -> str:
    """Убирает markdown-обёртку вокруг JSON."""

    if not text.startswith("`"):
        return text

    lines = text.splitlines()

    if lines:
        lines = lines[1:]

    if lines and lines[-1].strip().startswith("`"):
        lines = lines[:-1]

    return "\n".join(lines).strip()


def _decode_object(text: str) -> dict:
    """Находит и разбирает JSON-объект в ответе."""

    start = text.find("{")

    if start < 0:
        raise DecisionError("в ответе нет JSON-объекта")

    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as error:
        raise DecisionError(f"JSON не разобрался: {error.msg}") from error

    if not isinstance(data, dict):
        raise DecisionError("JSON должен быть объектом")

    return data


def _parse_answer(data: dict) -> AgentDecision:
    """Решение-ответ."""

    answer = data.get("text")

    if not isinstance(answer, str) or not answer.strip():
        raise DecisionError("в answer нет текста")

    return AgentDecision(action="answer", text=answer.strip())


def _parse_tool_call(item: dict) -> ToolCall:
    """Один вызов инструмента."""

    name = item.get("tool")
    args = item.get("args", {})

    if not isinstance(name, str) or not name.strip():
        raise DecisionError("у вызова нет инструмента")

    if not isinstance(args, dict):
        raise DecisionError("args должен быть объектом")

    return ToolCall(tool=name.strip(), args=args)


def _parse_tools(data: dict) -> AgentDecision:
    """Пакет вызовов."""

    raw_calls = data.get("calls")

    if not isinstance(raw_calls, list) or not raw_calls:
        raise DecisionError("в tools нужен непустой список calls")

    calls = []

    for item in raw_calls[:3]:
        if not isinstance(item, dict):
            raise DecisionError("каждый вызов должен быть объектом")

        calls.append(_parse_tool_call(item))

    return AgentDecision(action="tools", calls=tuple(calls))


def _parse_tool(data: dict) -> AgentDecision:
    """Одиночный вызов."""

    tool = data.get("tool")

    if not isinstance(tool, str) or not tool.strip():
        raise DecisionError("не указан инструмент")

    args = data.get("args", {})

    if not isinstance(args, dict):
        raise DecisionError("args должен быть объектом")

    return AgentDecision(
        action="tool",
        call=ToolCall(tool=tool.strip(), args=args),
    )


def parse_decision(raw: str) -> AgentDecision:
    """Разбирает ответ модели в решение агента."""

    data = _decode_object(_strip_fence(str(raw or "").strip()))
    action = data.get("action")

    if action == "answer":
        return _parse_answer(data)

    if action == "tools":
        return _parse_tools(data)

    if action != "tool":
        raise DecisionError("action должен быть tool, tools или answer")

    return _parse_tool(data)
