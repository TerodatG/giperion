# Giperion/terminal/core/agent/loop.py                              v001
# Цикл агента: решение модели → инструмент → наблюдение → ответ.
# Последнее изменение: первый вариант — только чтение, лимит шагов.

import json
import re
from pathlib import Path
from typing import Callable, Protocol

from terminal.core.agent import registry
from terminal.core.agent.context import (
    DecisionError,
    build_prompt,
    parse_decision,
)
from terminal.core.agent.protocol import (
    AgentResult,
    AgentStep,
    ToolCall,
    ToolResult,
)

DEFAULT_MAX_STEPS = 8

PATH_TOKEN = re.compile(
    r"[\w./\\-]+\.(?:py|md|json|jsonc|ui|txt|toml|cfg|ini|"
    r"ps1|bat|cmd|yml|yaml|html|css|js|ts|csv)\b",
    re.IGNORECASE,
)

STOPWORDS = {
    "чтобы", "какой", "какая", "какие", "сколько", "почему", "зачем",
    "можно", "нужно", "проект", "файл", "файлы", "прочитай", "найди",
    "покажи", "скажи", "ответь", "внутри", "сначала", "потом",
}


def grounding_calls(task: str, root: Path) -> list[ToolCall]:
    """Первый шаг без модели: дать ей реальные факты о проекте."""

    match = PATH_TOKEN.search(task)

    if match:
        path = match.group(0).strip(" .,:;()[]\"'")

        if path:
            return [ToolCall(tool="read_file", args={"path": path})]

    words = [
        word
        for word in re.findall(r"[А-Яа-яЁёA-Za-z]{4,}", task)
        if word.lower() not in STOPWORDS
    ]

    calls = [ToolCall(tool="list_dir", args={"path": "."})]

    if words:
        query = max(
            words,
            key=lambda word: (
                "_" in word,
                word.isascii(),
                len(word),
            ),
        )
        calls.append(
            ToolCall(tool="search_text", args={"query": query})
        )

    return calls


class Brain(Protocol):
    """Источник решений агента: модель или сценарий в тестах."""

    def decide(self, prompt: str) -> str:
        """Возвращает JSON-решение по промпту."""


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


def run_agent(
    task: str,
    brain: Brain,
    root: Path,
    max_steps: int = DEFAULT_MAX_STEPS,
    on_step: Callable[[AgentStep], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    require_tool_first: bool = True,
    ground_first: bool = True,
) -> AgentResult:
    """Выполняет задачу по шагам и возвращает итог и трейс."""

    clean_task = str(task or "").strip()

    if not clean_task:
        return AgentResult(error="Пустая задача.")

    steps: list[AgentStep] = []
    history: list[tuple[ToolCall, ToolResult]] = []

    def emit(step: AgentStep) -> None:
        steps.append(step)

        if on_step is not None:
            on_step(step)

    def stopped() -> bool:
        return bool(should_stop and should_stop())

    if ground_first:
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

            history.append((call, result))

    for index in range(1, max(max_steps, 1) + 1):
        if stopped():
            return AgentResult(steps=steps, cancelled=True)

        prompt = build_prompt(clean_task, history)

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
            )

        try:
            decision = parse_decision(raw)
        except DecisionError as error:
            emit(
                AgentStep(
                    index,
                    "error",
                    "Некорректное решение",
                    str(error),
                )
            )

            history.append(
                (
                    ToolCall(tool="format", args={}),
                    ToolResult(
                        False,
                        "Ответ не разобрался: "
                        f"{error}. Верни только JSON по схеме.",
                    ),
                )
            )

            continue

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
                history.append(
                    (
                        ToolCall(tool="policy", args={}),
                        ToolResult(
                            False,
                            "Сначала вызови list_dir, read_file или "
                            "search_text, а потом отвечай.",
                        ),
                    )
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

            return AgentResult(answer=decision.text, steps=steps)

        call = decision.call

        if call is None:
            continue

        result = registry.execute(root, call)

        emit(
            AgentStep(
                index,
                "tool",
                _call_title(call),
                _call_detail(result),
            )
        )

        history.append((call, result))

    return AgentResult(
        steps=steps,
        error=f"Достигнут лимит шагов: {max_steps}.",
    )
