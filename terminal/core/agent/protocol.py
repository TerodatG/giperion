# Giperion/terminal/core/agent/protocol.py                         v001
# Общие типы агента: инструменты, вызовы, результаты, шаги.
# Последнее изменение: первый вариант — только чтение.

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolSpec:
    """Описание инструмента, которое видит модель."""

    name: str
    description: str
    args: dict[str, str]
    risk: str = "read"
    required: tuple[str, ...] = ()


@dataclass(frozen=True)
class ToolCall:
    """Запрос модели на вызов инструмента."""

    tool: str
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Результат инструмента: текст и признак успеха."""

    ok: bool
    text: str


@dataclass(frozen=True)
class AgentStep:
    """Один шаг трейса: вызов инструмента или финальный ответ."""

    index: int
    kind: str
    title: str
    detail: str = ""


@dataclass(frozen=True)
class ApprovalRequest:
    """Действие, которое нельзя выполнять без согласия пользователя."""

    kind: str
    title: str
    detail: str
    path: str = ""
    new_text: str | None = None
    old_text: str | None = None


@dataclass(frozen=True)
class ApprovalResult:
    """Ответ пользователя: разрешение и, возможно, правка текста."""

    approved: bool
    text: str | None = None


@dataclass(frozen=True)
class AgentDecision:
    """Разобранное решение модели."""

    action: str
    text: str = ""
    call: ToolCall | None = None
    calls: tuple[ToolCall, ...] = ()


@dataclass
class AgentResult:
    """Итог работы агента."""

    answer: str = ""
    steps: list[AgentStep] = field(default_factory=list)
    error: str = ""
    cancelled: bool = False
