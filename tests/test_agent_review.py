# Giperion/tests/test_agent_review.py                                  v001
# Критик ответа: включение, замечания и пропуск OK.

import pytest

from terminal.core.agent import loop, settings
from terminal.core.agent.protocol import AgentResult


@pytest.fixture(autouse=True)
def _settings(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )


def _result():
    return AgentResult(answer="Файл изменён.", steps=[])


def test_review_is_off_by_default() -> None:
    """По умолчанию критик не запускается."""

    assert settings.review_enabled() is False

    settings.set_review_enabled(True)

    assert settings.review_enabled() is True


def test_review_appends_notes(monkeypatch) -> None:
    """Замечание критика попадает в ответ и шаги."""

    settings.set_review_enabled(True)
    monkeypatch.setattr(
        loop,
        "_run_agent_impl",
        lambda *args, **kwargs: AgentResult(
            answer="Не хватает запуска тестов."
        ),
    )

    result = _result()
    loop._maybe_review("поправь файл", object(), ".", result)

    assert "Проверка критика" in result.answer
    assert "запуска тестов" in result.answer
    assert result.steps[-1].kind == "review"


def test_review_skips_ok(monkeypatch) -> None:
    """Ответ «OK» ничего не добавляет."""

    settings.set_review_enabled(True)
    monkeypatch.setattr(
        loop,
        "_run_agent_impl",
        lambda *args, **kwargs: AgentResult(answer="OK"),
    )

    result = _result()
    loop._maybe_review("задача", object(), ".", result)

    assert result.answer == "Файл изменён."
    assert result.steps == []


def test_review_skips_disabled(monkeypatch) -> None:
    """При выключенной настройке модель не вызывается."""

    calls: list[int] = []
    monkeypatch.setattr(
        loop,
        "_run_agent_impl",
        lambda *args, **kwargs: calls.append(1) or AgentResult(),
    )

    result = _result()
    loop._maybe_review("задача", object(), ".", result)

    assert calls == []
    assert result.answer == "Файл изменён."
