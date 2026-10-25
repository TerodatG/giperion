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
