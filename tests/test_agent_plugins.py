# Giperion/tests/test_agent_plugins.py                               v002
# Плагины инструментов: манифест без исполнения и запуск в процессе.

import json
import time

from terminal.core.agent import registry, settings
from terminal.core.agent.plugin_runner import run_plugin_process
from terminal.core.agent.protocol import ToolCall

MODULE_CODE = '''
from terminal.core.agent.protocol import ToolResult


def handler(root, args):
    return ToolResult(True, "плагин: " + str(args.get("path", "")))
'''


def _install(
    tmp_path,
    monkeypatch,
    module_code: str = MODULE_CODE,
    manifest: dict | None = None,
) -> None:
    folder = tmp_path / "plugins"
    folder.mkdir(exist_ok=True)

    (folder / "word_count.py").write_text(
        module_code,
        encoding="utf-8",
    )

    document = {
        "name": "word_count",
        "description": "Проверочный плагин.",
        "args": {"path": "путь"},
        "required": ["path"],
        "risk": "read",
        "module": "word_count.py",
        "handler": "handler",
    }

    if manifest:
        document.update(manifest)

    (folder / "word_count.json").write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(registry, "PLUGIN_DIR", folder)
    registry.reload_plugins()


def test_plugin_is_loaded_when_enabled(tmp_path, monkeypatch) -> None:
    """Разрешённый плагин появляется в реестре и выполняется в процессе."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    _install(tmp_path, monkeypatch)

    spec = registry.get_spec("word_count")

    assert spec is not None
    assert spec.risk == "read"
    assert spec.required == ("path",)

    result = registry.execute(
        tmp_path,
        ToolCall(tool="word_count", args={"path": "a.txt"}),
    )

    assert result.ok
    assert "a.txt" in result.text

    registry.reload_plugins()


def test_plugin_is_ignored_when_disabled(tmp_path, monkeypatch) -> None:
    """Без разрешения манифест не читается."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: False)
    _install(tmp_path, monkeypatch)

    assert registry.get_spec("word_count") is None

    registry.reload_plugins()


def test_broken_manifest_is_skipped(tmp_path, monkeypatch) -> None:
    """Манифест без модуля не попадает в реестр."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    _install(tmp_path, monkeypatch, manifest={"module": "nope.py"})

    assert registry.get_spec("word_count") is None

    registry.reload_plugins()


def test_plugin_requires_approval_for_write(tmp_path, monkeypatch) -> None:
    """Плагин с risk=write требует подтверждения."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    _install(tmp_path, monkeypatch, manifest={"risk": "write"})

    assert registry.needs_approval(
        ToolCall(tool="word_count", args={"path": "a"})
    )

    registry.reload_plugins()


def test_loading_does_not_execute_plugin(tmp_path, monkeypatch) -> None:
    """Манифест читается без исполнения кода; падение видно только при вызове."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    _install(
        tmp_path,
        monkeypatch,
        module_code='raise RuntimeError("boom")\n',
    )

    assert registry.get_spec("word_count") is not None

    result = registry.execute(
        tmp_path,
        ToolCall(tool="word_count", args={"path": "a"}),
    )

    assert not result.ok
    assert "упал" in result.text or "без ответа" in result.text

    registry.reload_plugins()


def test_plugin_timeout_kills_process(tmp_path, monkeypatch) -> None:
    """Зависший плагин останавливается по таймауту."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    _install(
        tmp_path,
        monkeypatch,
        module_code=(
            "import time\n"
            "from terminal.core.agent.protocol import ToolResult\n"
            "def handler(root, args):\n"
            "    time.sleep(5)\n"
            "    return ToolResult(True, 'поздно')\n"
        ),
    )

    module = tmp_path / "plugins" / "word_count.py"
    started = time.monotonic()

    result = run_plugin_process(
        module,
        tmp_path,
        {},
        "handler",
        timeout=1,
    )

    assert not result.ok
    assert "не успел" in result.text
    assert time.monotonic() - started < 4

    registry.reload_plugins()


def test_plugin_env_has_no_secrets(monkeypatch) -> None:
    """Окружение плагина не содержит ключей и токенов."""

    from config import BASE_DIR
    from terminal.core.agent import sandbox

    monkeypatch.setenv("SECRET_TOKEN", "не-должен-попасть")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-не-должен")

    env = sandbox.plugin_env(BASE_DIR)

    assert "SECRET_TOKEN" not in env
    assert "OPENAI_API_KEY" not in env
    assert env["PYTHONPATH"] == str(BASE_DIR.resolve())
    assert env["AGENT_PLUGIN_SANDBOX"] == "1"
    assert sandbox.is_sensitive("MY_SECRET_TOKEN")
    assert not sandbox.is_sensitive("PATH")


def test_plugin_cannot_read_secret_from_env(tmp_path, monkeypatch) -> None:
    """Секрет родительского процесса не виден плагину."""

    monkeypatch.setenv("SECRET_TOKEN", "не-должен-попасть")

    _install(
        tmp_path,
        monkeypatch,
        module_code=(
            "import os\n"
            "from terminal.core.agent.protocol import ToolResult\n"
            "def handler(root, args):\n"
            "    return ToolResult(True, os.environ.get('SECRET_TOKEN', 'нет'))\n"
        ),
    )

    module = tmp_path / "plugins" / "word_count.py"
    result = run_plugin_process(module, tmp_path, {})

    assert result.ok
    assert result.text == "нет"

    registry.reload_plugins()


def test_plugin_runs_inside_project_folder(tmp_path, monkeypatch) -> None:
    """Рабочая папка плагина — проект, а не папка Терминала."""

    _install(
        tmp_path,
        monkeypatch,
        module_code=(
            "from pathlib import Path\n"
            "from terminal.core.agent.protocol import ToolResult\n"
            "def handler(root, args):\n"
            "    return ToolResult(True, str(Path.cwd()))\n"
        ),
    )

    module = tmp_path / "plugins" / "word_count.py"
    result = run_plugin_process(module, tmp_path, {})

    assert result.ok
    assert result.text == str(tmp_path.resolve())

    registry.reload_plugins()


def test_default_permissions_follow_risk(tmp_path, monkeypatch) -> None:
    """По умолчанию read получает только чтение, write — ещё и запись."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    _install(tmp_path, monkeypatch)

    read_spec = registry.get_spec("word_count")
    assert read_spec.permissions == ("fs:read",)

    _install(tmp_path, monkeypatch, manifest={"risk": "write"})
    write_spec = registry.get_spec("word_count")
    assert write_spec.permissions == ("fs:read", "fs:write")

    registry.reload_plugins()


def test_net_permission_requires_exec_risk(tmp_path, monkeypatch) -> None:
    """Сеть нельзя запросить при risk=read."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    _install(
        tmp_path,
        monkeypatch,
        manifest={"risk": "read", "permissions": ["net"]},
    )

    assert registry.get_spec("word_count") is None

    registry.reload_plugins()


def test_unsafe_plugin_needs_setting(tmp_path, monkeypatch) -> None:
    """Сеть и запуск программ грузятся только с отдельным разрешением."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    monkeypatch.setattr(
        settings,
        "allow_unsafe_plugins",
        lambda: False,
    )
    _install(
        tmp_path,
        monkeypatch,
        manifest={"risk": "exec", "permissions": ["fs:read", "net"]},
    )

    assert registry.get_spec("word_count") is None

    monkeypatch.setattr(
        settings,
        "allow_unsafe_plugins",
        lambda: True,
    )
    registry.reload_plugins()

    spec = registry.get_spec("word_count")
    assert spec is not None
    assert "net" in spec.permissions

    registry.reload_plugins()


def test_sandbox_job_limits_do_not_break_process(tmp_path) -> None:
    """Прикрепление к job не мешает процессу завершиться."""

    import subprocess
    import sys

    from terminal.core.agent import sandbox

    process = subprocess.Popen(
        [sys.executable, "-c", "print('ok')"],
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )

    job = sandbox.attach(process.pid, memory_mb=256, cpu_seconds=5)

    try:
        output, _ = process.communicate(timeout=10)
    finally:
        sandbox.close(job)

    assert output.strip() == "ok"
    assert sandbox.available() == (sys.platform == "win32")


def test_quota_exit_has_clear_message() -> None:
    """Код завершения по квоте CPU переводится в понятную фразу."""

    from terminal.core.agent.plugin_runner import _exit_hint

    assert "лимит времени CPU" in _exit_hint(0xC0000044)
    assert _exit_hint(1) == ""


def test_memory_limit_stops_greedy_plugin(tmp_path, monkeypatch) -> None:
    """Плагин, просящий больше лимита памяти, падает с MemoryError."""

    import pytest

    from terminal.core.agent import sandbox

    if not sandbox.available():
        pytest.skip("Job Objects доступны только на Windows")

    _install(
        tmp_path,
        monkeypatch,
        module_code=(
            "from terminal.core.agent.protocol import ToolResult\n"
            "def handler(root, args):\n"
            "    data = bytearray(900 * 1024 * 1024)\n"
            "    return ToolResult(True, str(len(data)))\n"
        ),
    )

    module = tmp_path / "plugins" / "word_count.py"
    result = run_plugin_process(
        module,
        tmp_path,
        {},
        memory_mb=256,
        cpu_seconds=10,
    )

    assert not result.ok
    assert "MemoryError" in result.text or "упал" in result.text

    registry.reload_plugins()
