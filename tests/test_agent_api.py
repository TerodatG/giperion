# Giperion/tests/test_agent_api.py                                     v001
# HTTP API терминала: токен, валидация и read-only запуск.

from types import SimpleNamespace

from tools import agent_api


def test_token_is_created_and_checked(tmp_path, monkeypatch) -> None:
    """Токен создаётся в файле и проверяется через Bearer."""

    monkeypatch.delenv("GIPERION_API_TOKEN", raising=False)
    monkeypatch.setattr(
        agent_api,
        "TOKEN_FILE",
        tmp_path / "token",
    )

    value = agent_api.token()

    assert value
    assert agent_api.authorized("Bearer " + value)
    assert not agent_api.authorized("Bearer wrong")
    assert not agent_api.authorized("")


def test_env_token_wins(tmp_path, monkeypatch) -> None:
    """Переменная окружения важнее файла."""

    monkeypatch.setenv("GIPERION_API_TOKEN", "env-token")
    monkeypatch.setattr(
        agent_api,
        "TOKEN_FILE",
        tmp_path / "token",
    )

    assert agent_api.token() == "env-token"
    assert agent_api.authorized("Bearer env-token")


def test_task_is_read_only() -> None:
    """Запись и пустая задача отклоняются без запуска модели."""

    assert not agent_api.handle_task({})["ok"]
    assert not agent_api.handle_task(
        {"task": "поправь файл", "policy": "confirm"}
    )["ok"]


def test_task_runs_agent(monkeypatch, tmp_path) -> None:
    """Успешная задача возвращает ответ и модель."""

    calls = {}

    monkeypatch.setattr(
        agent_api,
        "build_brain",
        lambda model, provider: (object(), "test/model"),
    )
    monkeypatch.setattr(
        agent_api,
        "BASE_DIR",
        tmp_path,
    )

    def fake_run(task, brain, root, **kwargs):
        calls["task"] = task
        calls["policy"] = kwargs.get("policy")

        return SimpleNamespace(
            answer="готово",
            error="",
            cancelled=False,
            steps=[1, 2],
        )

    monkeypatch.setattr(agent_api, "run_agent", fake_run)

    result = agent_api.handle_task(
        {"task": "найди файл", "max_steps": 3}
    )

    assert result["ok"]
    assert result["answer"] == "готово"
    assert result["steps"] == 2
    assert calls["policy"] == "read"
