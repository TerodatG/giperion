# Giperion/tests/test_agent_plugins_dialog.py                           v001
# Плагины: манифесты, разрешения, отзыв и экран.

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from terminal.core.agent import plugins


def _plugin(folder, name="word"):
    target = folder / name
    target.mkdir(parents=True)
    (target / f"{name}.json").write_text(
        json.dumps(
            {
                "name": name,
                "description": "Считает слова",
                "risk": "read",
                "permissions": ["fs:read"],
                "module": "plugin.py",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return target


def test_list_and_revoke(tmp_path, monkeypatch) -> None:
    """Плагин находится по манифесту и удаляется по имени."""

    folder = tmp_path / "agent_tools"
    target = _plugin(folder)
    monkeypatch.setattr(plugins, "PLUGIN_DIR", folder)

    items = plugins.list_installed()

    assert items[0]["name"] == "word"
    assert items[0]["permissions"] == ["fs:read"]
    assert plugins.revoke("WORD")
    assert not target.exists()
    assert not plugins.revoke("missing")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


def test_dialog_shows_permissions(qapp, monkeypatch) -> None:
    """Экран показывает риск и разрешения."""

    from terminal.ui.plugins_dialog import PluginsDialog

    monkeypatch.setattr(
        plugins,
        "list_installed",
        lambda *args, **kwargs: [
            {
                "name": "word",
                "description": "Считает слова",
                "risk": "read",
                "permissions": ["fs:read"],
                "folder": "data/agent_tools/word",
            }
        ],
    )

    dialog = PluginsDialog(None)

    try:
        assert dialog.list.count() == 1
        assert "fs:read" in dialog.detail.toPlainText()
    finally:
        dialog.close()
