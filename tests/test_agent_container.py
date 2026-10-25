# Giperion/tests/test_agent_container.py                              v001
# Песочница AppContainer: подготовка, окружение и выбор режима.

import json
import sys
from pathlib import Path

import pytest

from terminal.core.agent import container
from terminal.core.agent import plugin_runner


def test_child_env_filters_secrets(monkeypatch) -> None:
    """Окружение контейнера не содержит токенов и указывает TEMP."""

    monkeypatch.setenv("SECRET_TOKEN", "нельзя")
    monkeypatch.setenv("OPENAI_API_KEY", "тоже")

    env = container.child_env()

    assert "SECRET_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert env["TEMP"] == str(container.TEMP_DIR)
    assert env["AGENT_PLUGIN_SANDBOX"] == "appcontainer"
    assert env["PYTHONPATH"]


def test_available_requires_marker(tmp_path, monkeypatch) -> None:
    """Без маркера и python.exe контейнер не считается готовым."""

    python_dir = tmp_path / "py"
    marker = python_dir / ".ready"

    monkeypatch.setattr(container, "PYTHON_DIR", python_dir)
    monkeypatch.setattr(container, "MARKER", marker)

    assert not container.available()

    python_dir.mkdir()
    (python_dir / "python.exe").write_bytes(b"")
    marker.write_text("3.13.0", encoding="utf-8")

    assert container.available() is (sys.platform == "win32")


def test_prepare_copies_python(tmp_path, monkeypatch) -> None:
    """Подготовка копирует Python без site-packages и пишет маркер."""

    source = tmp_path / "base"
    (source / "Lib" / "site-packages").mkdir(parents=True)
    (source / "Lib" / "site-packages" / "big.py").write_text("x")
    (source / "Lib" / "os.py").write_text("y")
    (source / "python.exe").write_bytes(b"exe")

    python_dir = tmp_path / "sandbox"
    marker = python_dir / ".ready"

    monkeypatch.setattr(container, "PYTHON_DIR", python_dir)
    monkeypatch.setattr(container, "MARKER", marker)
    monkeypatch.setattr(container, "TEMP_DIR", tmp_path / "temp")
    monkeypatch.setattr(
        container,
        "ensure_profile",
        lambda: (None, "S-1-15-2-1"),
    )
    monkeypatch.setattr(container, "grant", lambda sid: ["права выданы"])
    monkeypatch.setattr(
        container,
        "run_text",
        lambda *args, **kwargs: (0, "container-ok"),
    )

    steps = container.prepare(source=source)

    assert (python_dir / "python.exe").is_file()
    assert (python_dir / "Lib" / "os.py").is_file()
    assert not (python_dir / "Lib" / "site-packages").exists()
    assert marker.read_text(encoding="utf-8").startswith("3.13")
    assert any("скопирован" in step for step in steps)
    assert "проверка: container-ok" in steps


def test_prepare_reports_failed_selftest(tmp_path, monkeypatch) -> None:
    """Если Python в контейнере не стартует, подготовка падает."""

    source = tmp_path / "base"
    source.mkdir()
    (source / "python.exe").write_bytes(b"exe")

    monkeypatch.setattr(container, "PYTHON_DIR", tmp_path / "sandbox")
    monkeypatch.setattr(container, "MARKER", tmp_path / "sandbox" / ".ready")
    monkeypatch.setattr(container, "TEMP_DIR", tmp_path / "temp")
    monkeypatch.setattr(
        container,
        "ensure_profile",
        lambda: (None, "S-1-15-2-1"),
    )
    monkeypatch.setattr(container, "grant", lambda sid: [])
    monkeypatch.setattr(
        container,
        "run_text",
        lambda *args, **kwargs: (0xC0000142, ""),
    )

    with pytest.raises(container.ContainerError):
        container.prepare(source=source)


def test_runner_uses_container(tmp_path, monkeypatch) -> None:
    """В режиме appcontainer плагин запускается копией Python."""

    captured: dict = {}

    monkeypatch.setattr(
        plugin_runner,
        "_sandbox_mode",
        lambda: "appcontainer",
    )
    monkeypatch.setattr(container, "available", lambda: True)
    monkeypatch.setattr(
        container,
        "run_text",
        lambda args, cwd, timeout: (
            captured.update(args=args, cwd=cwd)
            or (0, json.dumps({"ok": True, "text": "из контейнера"}))
        ),
    )

    result = plugin_runner.run_plugin_process(
        tmp_path / "plugin.py",
        tmp_path,
        {"path": "a"},
        "handler",
        permissions=("fs:read",),
    )

    assert result.ok
    assert result.text == "из контейнера"
    assert "terminal.core.agent.plugin_runner" in captured["args"]
    assert captured["cwd"] == tmp_path


def test_runner_reports_missing_container(tmp_path, monkeypatch) -> None:
    """Неготовый контейнер даёт понятную подсказку."""

    monkeypatch.setattr(
        plugin_runner,
        "_sandbox_mode",
        lambda: "appcontainer",
    )
    monkeypatch.setattr(container, "available", lambda: False)

    result = plugin_runner.run_plugin_process(
        tmp_path / "plugin.py",
        tmp_path,
        {},
    )

    assert not result.ok
    assert "setup_plugin_container" in result.text


def test_sandbox_mode_setting(tmp_path, monkeypatch) -> None:
    """Режим песочницы сохраняется и проверяется."""

    from terminal.core.agent import settings

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.plugin_sandbox() == "process"

    settings.set_plugin_sandbox("appcontainer")
    assert settings.plugin_sandbox() == "appcontainer"

    settings.set_plugin_sandbox("process")
    assert settings.plugin_sandbox() == "process"

    with pytest.raises(ValueError):
        settings.set_plugin_sandbox("контейнер")
