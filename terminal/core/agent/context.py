# Giperion/terminal/core/agent/context.py                           v001
# Сборка промпта агента и разбор его JSON-решения.
# Последнее изменение: первый вариант — строгий JSON без function calling.

import json
from dataclasses import dataclass

from terminal.core.agent.protocol import (
    AgentDecision,
    ToolCall,
    ToolResult,
)
from terminal.core.agent.registry import tools_prompt

MAX_OBSERVATION = 4000
MAX_HISTORY = 24000

SYSTEM_PROMPT = (
    "Ты — агент «Терминал» в проекте Giperion. Ты умеешь читать файлы, "
    "точечно менять их и запускать тесты. Любая запись и запуск тестов "
    "выполняются только после подтверждения пользователя.\n\n"
    "Отвечай ОДНИМ JSON-объектом и больше ничем:\n"
    '{"action": "tool", "tool": "read_file", "args": {"path": "README.md"}}\n'
    '{"action": "tool", "tool": "apply_patch", "args": {"path": "a.py", '
    '"old": "старый текст", "new": "новый текст"}}\n'
    '{"action": "answer", "text": "короткий ответ по-русски"}\n\n'
    "Правила:\n"
    "- не выдумывай содержимое файлов: сначала прочитай или найди;\n"
    "- нельзя отвечать, что ты «прочитал файл», если не было вызова "
    "read_file;\n"
    "- если задача про проект, первый шаг — инструмент, а не ответ;\n"
    "- перед правкой прочитай файл и меняй точечно через apply_patch;\n"
    "- не переписывай файл целиком, если хватает замены фрагмента;\n"
    "- после правки запусти run_tests и посмотри на результат;\n"
    "- если тесты упали — прочитай ошибку, исправь и запусти снова;\n"
    "- для состояния репозитория используй git_status и git_diff;\n"
    "- коммить только изменённый файл и только после успешных тестов;\n"
    "- откат файла — git_restore, если правка его сломала;\n"
    "- run_command — только для разрешённых команд из описания;\n"
    "- ask_subagent — поручить чтение подзадачи помощнику, он не пишет;\n"
    "- не трогай файлы, не относящиеся к задаче;\n"
    "- если действие отклонили, не повторяй его, предложи другой путь;\n"
    "- путь всегда относительный, внутри проекта;\n"
    "- в answer ссылайся на прочитанные файлы и результат тестов;\n"
    "- без markdown, без пояснений вокруг JSON."
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


def build_prompt(
    task: str,
    history: list[tuple[ToolCall, ToolResult]],
) -> str:
    """Собирает промпт: правила, инструменты, задача и прошлые шаги."""

    parts = [
        SYSTEM_PROMPT,
        "Доступные инструменты:\n" + tools_prompt(),
        f"Задача: {task.strip()}",
    ]

    if history:
        lines = ["Выполненные шаги:"]

        for number, (call, result) in enumerate(history, start=1):
            args = json.dumps(call.args, ensure_ascii=False)
            lines.append(f"{number}. {call.tool}({args})")
            lines.append(
                "   результат: " + _shorten(result.text, 1200)
            )

        block = "\n".join(lines)
        parts.append(_shorten(block, MAX_HISTORY))
    else:
        parts.append("Выполненных шагов пока нет.")

    parts.append("Следующий шаг — один JSON-объект:")

    return "\n\n".join(parts)


def parse_decision(raw: str) -> AgentDecision:
    """Разбирает ответ модели в решение агента."""

    text = str(raw or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    start = text.find("{")

    if start < 0:
        raise DecisionError("в ответе нет JSON-объекта")

    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as error:
        raise DecisionError(f"JSON не разобрался: {error.msg}") from error

    if not isinstance(data, dict):
        raise DecisionError("JSON должен быть объектом")

    action = data.get("action")

    if action == "answer":
        answer = data.get("text")

        if not isinstance(answer, str) or not answer.strip():
            raise DecisionError("в answer нет текста")

        return AgentDecision(action="answer", text=answer.strip())

    if action != "tool":
        raise DecisionError("action должен быть tool или answer")

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
