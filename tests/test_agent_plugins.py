# Giperion/tests/test_agent_plugins.py                               v001
# Плагины инструментов: только по явному разрешению.

from terminal.core.agent import registry, settings
from terminal.core.agent.protocol import ToolCall

PLUGIN_CODE = '''
from terminal.core.agent.protocol import ToolResult


def handler(root, args):
    return ToolResult(True, "плагин: " + str(args.get("path", "")))


TOOL = {
    "name": "word_count",
    "description": "Проверочный плагин.",
    "args": {"path": "путь"},
    "required": ["path"],
    "risk": "read",
    "handler": handler,
}
'''


def _install(tmp_path, monkeypatch, code: str = PLUGIN_CODE) -> None:
    folder = tmp_path / "plugins"
    folder.mkdir(exist_ok=True)
    (folder / "word_count.py").write_text(code, encoding="utf-8")

    monkeypatch.setattr(registry, "PLUGIN_DIR", folder)
    registry.reload_plugins()


def test_plugin_is_loaded_when_enabled(tmp_path, monkeypatch) -> None:
    """Разрешённый плагин появляется в реестре и выполняется."""

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
    """Без разрешения код плагина не загружается."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: False)
    _install(tmp_path, monkeypatch)

    assert registry.get_spec("word_count") is None

    registry.reload_plugins()


def test_broken_plugin_is_skipped(tmp_path, monkeypatch) -> None:
    """Битый плагин не роняет реестр."""

    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    _install(tmp_path, monkeypatch, code="TOOL = 'не словарь'")

    assert registry.get_spec("word_count") is None

    registry.reload_plugins()


def test_plugin_requires_approval_for_write(tmp_path, monkeypatch) -> None:
    """Плагин с risk=write требует подтверждения."""

    code = PLUGIN_CODE.replace('"risk": "read"', '"risk": "write"')
    monkeypatch.setattr(settings, "plugins_enabled", lambda: True)
    _install(tmp_path, monkeypatch, code=code)

    assert registry.needs_approval(
        ToolCall(tool="word_count", args={"path": "a"})
    )

    registry.reload_plugins()
