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
    monkeypatch.setattr(
        agent_api,
        "CALL_LOG_FILE",
        tmp_path / "calls.jsonl",
    )

    result = agent_api.handle_task(
        {"task": "найди файл", "max_steps": 3}
    )

    assert result["ok"]
    assert result["answer"] == "готово"
    assert result["steps"] == 2
    assert len(result["trace"]) == 2
    assert calls["policy"] == "read"
    assert (tmp_path / "calls.jsonl").is_file()


def test_project_is_limited_to_workspace(tmp_path, monkeypatch) -> None:
    """API не выпускает задачу за рабочую папку."""

    monkeypatch.setattr(agent_api, "BASE_DIR", tmp_path)
    inside = tmp_path / "sub"
    inside.mkdir()

    assert agent_api.project_root("sub") == inside.resolve()
    assert agent_api.project_root(str(tmp_path)) == tmp_path.resolve()
    assert agent_api.project_root("../") is None
    assert agent_api.project_root(str(tmp_path.parent)) is None
    assert agent_api.project_root("missing") is None


def test_rate_limit_counts_requests(monkeypatch) -> None:
    """Больше лимита запросов за минуту не проходит."""

    monkeypatch.setattr(agent_api, "_RATE", {})

    allowed = [
        agent_api.allow_request("127.0.0.1", now=100.0)
        for _ in range(agent_api.RATE_LIMIT)
    ]

    assert all(allowed)
    assert not agent_api.allow_request("127.0.0.1", now=100.0)
    assert agent_api.allow_request(
        "127.0.0.1",
        now=100.0 + agent_api.RATE_WINDOW + 1,
    )


def test_call_log_redacts_and_has_no_token(tmp_path, monkeypatch) -> None:
    """Журнал вызовов не хранит токен и секреты задачи."""

    target = tmp_path / "calls.jsonl"
    monkeypatch.setattr(agent_api, "CALL_LOG_FILE", target)

    agent_api.log_call(
        "найди api_key = sk-1234567890abcdef",
        {"ok": True, "steps": 3},
        0.25,
        tmp_path,
        "127.0.0.1",
    )

    text = target.read_text(encoding="utf-8")

    assert "sk-1234567890abcdef" not in text
    assert "[скрыто]" in text
    assert "127.0.0.1" in text
    assert "elapsed_ms" in text
