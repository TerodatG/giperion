# Giperion/tests/test_agent_context_budget.py                         v001
# Бюджет промпта из контекста модели.

from terminal.core.agent.context_budget import (
    budget_for_model,
    budget_for_tokens,
    normalize_tokens,
)


def test_normalize_tokens() -> None:
    """Значения меньше 2000 считаются тысячами."""

    assert normalize_tokens(32) == 32_000
    assert normalize_tokens(200_000) == 200_000
    assert normalize_tokens("4096") == 4096
    assert normalize_tokens(None) == 0
    assert normalize_tokens(-5) == 0


def test_budget_for_tokens() -> None:
    """32k токенов дают привычные 60k символов, есть границы."""

    assert budget_for_tokens(0) == 0
    assert 55_000 <= budget_for_tokens(32_768) <= 65_000
    assert budget_for_tokens(200_000) == 375_000
    assert budget_for_tokens(10**9) == 2_000_000


def test_budget_for_model_falls_back() -> None:
    """Без контекста модели остаётся ручное значение."""

    assert budget_for_model(None, 60_000) == 60_000
    assert budget_for_model({}, 60_000) == 60_000
    assert budget_for_model({"context_limit": 0}, 60_000) == 60_000
    assert budget_for_model({"context_limit": 32}, 1_000) == 60_000
