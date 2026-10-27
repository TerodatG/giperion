# Giperion/tests/test_agent_budget.py                                 v001
# Бюджет задачи: лимиты токенов и стоимости, остановка и журнал.

import json
import time

from terminal.core.agent.budget import (
    BudgetLimits,
    cost_of,
    describe,
    exceeded,
    warning,
)
from terminal.core.agent.loop import run_agent
from terminal.core.agent.protocol import AgentDecision, ToolCall
from terminal.core.agent.providers import (
    NativeBrain,
    OpenAICompatibleProvider,
)
from terminal.ui.agent_job import AgentJob


def test_cost_is_computed_per_million() -> None:
    """Стоимость считается по ценам за миллион токенов."""

    limits = BudgetLimits(price_in=3.0, price_out=15.0)

    assert cost_of(1_000_000, 0, limits) == 3.0
    assert cost_of(0, 1_000_000, limits) == 15.0
    assert cost_of(1000, 1000, limits) == 0.018
    assert cost_of(-5, -5, limits) == 0.0


def test_free_model_costs_nothing() -> None:
    """Без цен локальная модель ничего не стоит."""

    assert cost_of(50_000, 2_000, BudgetLimits()) == 0.0


def test_exceeded_reports_tokens_and_cost() -> None:
    """Причина остановки различает лимит токенов и лимит денег."""

    assert exceeded(BudgetLimits(tokens=1000), 999, 0.0) == ""
    assert "токенов" in exceeded(BudgetLimits(tokens=1000), 1000, 0.0)

    assert exceeded(BudgetLimits(cost=0.5), 10, 0.499) == ""
    assert "$" in exceeded(BudgetLimits(cost=0.5), 10, 0.5)

    # Без лимитов не останавливаемся никогда.
    assert exceeded(BudgetLimits(), 10**9, 10**6) == ""


def test_describe_is_short() -> None:
    """Описание бюджета для окна."""

    assert describe(BudgetLimits()) == "без лимита"
    assert describe(BudgetLimits(tokens=5000)) == "5000 токенов"
    assert describe(BudgetLimits(tokens=5000, cost=1.5)) == (
        "5000 токенов · $1.50"
    )


def test_warning_at_eighty_percent() -> None:
    """Предупреждение появляется до остановки."""

    limits = BudgetLimits(tokens=1000, cost=1.0)

    assert warning(limits, 100, 0.0) == ""
    assert "1000" in warning(limits, 800, 0.0)
    assert "80%" in warning(limits, 800, 0.0)
    assert "$" in warning(limits, 0, 0.9)
    assert warning(BudgetLimits(), 10**9, 10**6) == ""


def test_native_brain_counts_cost() -> None:
    """Мозг копит стоимость по usage провайдера."""

    def transport(url, key, payload, timeout):
        return {
            "choices": [{"message": {"content": "ок"}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        }

    provider = OpenAICompatibleProvider(
        "http://localhost/v1",
        "secret",
        "test-model",
        transport=transport,
    )

    brain = NativeBrain(
        provider,
        BudgetLimits(price_in=2.0, price_out=10.0),
    )

    brain.decide("раз")
    brain.decide("два")

    assert brain.total_tokens == 3000
    assert abs(brain.cost - (0.002 + 0.005) * 2) < 1e-9


class SpendingBrain:
    """Мозг, который тратит заданное число токенов за решение."""

    native = True

    def __init__(self, decisions, per_call: int) -> None:
        self.decisions = list(decisions)
        self.per_call = per_call
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost = 0.0
        self.prompts: list[str] = []

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def decide(self, prompt: str):
        self.prompts.append(prompt)
        self.prompt_tokens += self.per_call

        return self.decisions.pop(0)


def test_budget_stops_before_tool_call(tmp_path) -> None:
    """Если бюджет исчерпан, действие не выполняется."""

    target = tmp_path / "a.txt"
    target.write_text("старое", encoding="utf-8")

    brain = SpendingBrain(
        [
            AgentDecision(
                action="tools",
                calls=(ToolCall("read_file", {"path": "a.txt"}),),
            )
        ],
        per_call=400,
    )

    result = run_agent(
        "прочитай",
        brain,
        tmp_path,
        ground_first=False,
        budget=BudgetLimits(tokens=300),
    )

    assert "бюджет токенов" in result.error
    assert result.error.endswith("Задача остановлена.")
    assert [step.kind for step in result.steps] == ["budget"]
    assert "400" in result.steps[0].detail


def test_budget_allows_final_answer(tmp_path) -> None:
    """Ответ после исчерпания бюджета не выбрасывается."""

    brain = SpendingBrain(
        [AgentDecision(action="answer", text="готово")],
        per_call=400,
    )

    result = run_agent(
        "ответь",
        brain,
        tmp_path,
        ground_first=False,
        require_tool_first=False,
        budget=BudgetLimits(tokens=300),
    )

    assert result.answer == "готово"
    assert result.error == ""


def test_budget_without_limits_never_stops(tmp_path) -> None:
    """Нулевые лимиты означают «без ограничений»."""

    brain = SpendingBrain(
        [
            AgentDecision(
                action="tools",
                calls=(ToolCall("list_dir", {"path": "."}),),
            ),
            AgentDecision(action="answer", text="ок"),
        ],
        per_call=10**6,
    )

    result = run_agent(
        "посмотри",
        brain,
        tmp_path,
        ground_first=False,
        budget=BudgetLimits(),
    )

    assert result.answer == "ок"


def _wait_for(predicate, timeout: float = 3.0) -> None:
    deadline = time.time() + timeout

    while time.time() < deadline:
        if predicate():
            return

        time.sleep(0.02)

    raise AssertionError("Не дождались состояния")


def test_job_reports_tokens_and_cost(tmp_path, monkeypatch) -> None:
    """Прогон пишет токены и стоимость в журнал и отдаёт окну."""

    from terminal.core.agent import runs

    journal = tmp_path / "agent_runs.jsonl"
    monkeypatch.setattr(runs, "RUNS_FILE", journal)

    brain = SpendingBrain(
        [AgentDecision(action="answer", text="готово")],
        per_call=750,
    )
    brain.cost = 0.25

    job = AgentJob(
        "задача",
        brain,
        tmp_path,
        max_steps=2,
        model_name="Тест",
        persist=False,
        budget=BudgetLimits(tokens=10_000, price_in=1.0),
    )

    _wait_for(lambda: job.done)

    assert job.tokens == 750
    assert job.cost == 0.25
    assert job.answer == "готово"

    records = [
        json.loads(line)
        for line in journal.read_text(encoding="utf-8").splitlines()
    ]

    assert records[0]["tokens"] == 750
    assert records[0]["cost"] == 0.25


def test_budget_settings_roundtrip(tmp_path, monkeypatch) -> None:
    """Лимиты и цены сохраняются и читаются из файла настроек."""

    from terminal.core.agent import settings

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.budget_limits() == BudgetLimits()

    settings.save_budget_limits(50_000, 1.25, 2.5, 10.0)
    limits = settings.budget_limits()

    assert limits.tokens == 50_000
    assert limits.cost == 1.25
    assert limits.price_in == 2.5
    assert limits.price_out == 10.0

    # Мусор в файле не ломает чтение.
    (tmp_path / "agent_settings.json").write_text(
        json.dumps(
            {
                "token_limit": "много",
                "cost_limit": -5,
                "price_in": None,
                "price_out": True,
            }
        ),
        encoding="utf-8",
    )

    assert settings.budget_limits() == BudgetLimits()
