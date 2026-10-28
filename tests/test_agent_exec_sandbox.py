# Giperion/tests/test_agent_exec_sandbox.py                             v001
# Запуск команд: чистое окружение, прокси-заглушка и режимы.

from types import SimpleNamespace

from terminal.core.agent import exec_sandbox


def test_env_has_no_secrets_and_blocks_proxy(monkeypatch, tmp_path) -> None:
    """Секреты не наследуются, HTTP идёт в мёртвый прокси."""

    monkeypatch.setenv("AGENT_API_KEY", "secret-value")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setattr(
        exec_sandbox,
        "TEMP_DIR",
        tmp_path / "tmp",
    )

    env = exec_sandbox.env_for(tmp_path)

    assert "AGENT_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert env["HTTPS_PROXY"] == exec_sandbox.DEAD_PROXY
    assert env["GIPERION_EGRESS"] == "deny"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_run_captures_output(tmp_path) -> None:
    """Процесс запускается без shell и отдаёт код/вывод."""

    import sys

    result = exec_sandbox.run(
        [sys.executable, "-c", "print('sandbox-ok')"],
        tmp_path,
        timeout=30,
    )

    assert result.code == 0
    assert "sandbox-ok" in result.output
    assert not result.timed_out


def test_identical_command_is_cached(tmp_path) -> None:
    """Повтор той же команды при неизменном проекте берётся из кеша."""

    import sys

    args = [sys.executable, "-c", "print('cache-me')"]
    first = exec_sandbox.run(args, tmp_path, timeout=30)
    second = exec_sandbox.run(args, tmp_path, timeout=30)

    assert first.code == 0
    assert not first.cached
    assert second.cached
    assert second.output == first.output


def test_run_python_process_mode_falls_back(monkeypatch, tmp_path) -> None:
    """В режиме process AppContainer не используется."""

    calls = []

    monkeypatch.setattr(exec_sandbox, "isolation", lambda: "process")
    monkeypatch.setattr(
        exec_sandbox,
        "run",
        lambda args, cwd, timeout=300: calls.append(args)
        or SimpleNamespace(
            code=0,
            output="ок",
            timed_out=False,
            isolated=False,
        ),
    )

    result = exec_sandbox.run_python(["python", "-m", "pytest"], tmp_path)

    assert result.code == 0
    assert calls == [["python", "-m", "pytest"]]


def test_non_python_command_uses_container(monkeypatch, tmp_path) -> None:
    """git и другие команды идут в командный AppContainer."""

    from terminal.core.agent import container

    calls = {}

    monkeypatch.setattr(exec_sandbox, "isolation", lambda: "auto")
    monkeypatch.setattr(container, "available", lambda: True)
    monkeypatch.setattr(
        container,
        "grant_commands",
        lambda root, exe: calls.update(grant=(root, exe)),
    )

    def fake_run(args, cwd, **kwargs):
        calls.update(args=args, cwd=cwd, kwargs=kwargs)

        return 0, "ok"

    monkeypatch.setattr(container, "run_text", fake_run)

    result = exec_sandbox.run(["git", "status"], tmp_path)

    assert result.code == 0
    assert result.isolated
    assert calls["args"] == ["status"]
    assert calls["kwargs"]["profile"] == container.COMMAND_PROFILE


def test_appcontainer_mode_without_setup(monkeypatch, tmp_path) -> None:
    """Без подготовленного контейнера режим appcontainer честно отказывает."""

    from terminal.core.agent import container

    monkeypatch.setattr(exec_sandbox, "isolation", lambda: "appcontainer")
    monkeypatch.setattr(container, "available", lambda: False)

    result = exec_sandbox.run_python(["python", "-m", "pytest"], tmp_path)

    assert result.code == 1
    assert "AppContainer" in result.output


def test_is_python_compares_real_executable(tmp_path) -> None:
    """Python определяется по resolved-пути."""

    import sys

    assert exec_sandbox.is_python([sys.executable, "-c", "1"])
    assert not exec_sandbox.is_python([sys.executable + "x", "-c", "1"])
    assert not exec_sandbox.is_python([])
