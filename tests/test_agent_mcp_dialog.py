# Giperion/tests/test_agent_mcp_dialog.py                              v001
# Окно MCP: сохранение allowlist и отказ на битом JSON.

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from terminal.core.agent import mcp


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def _config(tmp_path, monkeypatch):
    path = tmp_path / "agent_mcp.json"
    path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "name": "web",
                        "command": "python",
                        "tools": ["fetch"],
                        "domains": ["example.com"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mcp, "CONFIG_FILE", path)

    return path


def test_dialog_saves_allowlist(tmp_path, monkeypatch, qapp) -> None:
    """Окно пишет tools/domains и перезагружает MCP."""

    from terminal.ui.mcp_dialog import McpDialog

    path = _config(tmp_path, monkeypatch)
    dialog = McpDialog(None)

    try:
        dialog.editor.setPlainText(
            json.dumps(
                {
                    "servers": [
                        {
                            "name": "web",
                            "command": "python",
                            "tools": ["fetch", "search"],
                            "domains": ["*.example.com"],
                        }
                    ]
                }
            )
        )
        dialog._save()

        saved = json.loads(path.read_text(encoding="utf-8"))

        assert saved["servers"][0]["tools"] == ["fetch", "search"]
        assert "Сохранено" in dialog.status.text()
    finally:
        dialog.close()


def test_dialog_rejects_broken_json(tmp_path, monkeypatch, qapp) -> None:
    """Битый JSON не перезаписывает файл."""

    from terminal.ui.mcp_dialog import McpDialog

    path = _config(tmp_path, monkeypatch)
    before = path.read_text(encoding="utf-8")
    dialog = McpDialog(None)

    try:
        dialog.editor.setPlainText("{ не json")
        dialog._save()

        assert path.read_text(encoding="utf-8") == before
        assert "JSON не разобрался" in dialog.status.text()
    finally:
        dialog.close()
