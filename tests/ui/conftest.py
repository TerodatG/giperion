# Giperion/tests/ui/conftest.py                                       v001
# Общие фикстуры оконных тестов: Qt, состояние и главное окно.
# Последнее изменение: вынесено из test_gui_smoke.

import copy
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Одно приложение Qt на всю сессию тестов."""

    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


@pytest.fixture(autouse=True)
def reset_pending_state():
    """Не даёт незавершённым действиям переходить между тестами."""

    from terminal.core import pending_state

    pending_state.set_state(pending_state.new_state())

    yield

    pending_state.set_state(pending_state.new_state())


@pytest.fixture()
def window(qapp, tmp_path, monkeypatch):
    """Создаёт настоящее окно с изолированными настройками."""

    import gui
    from terminal.core import chat_context
    from terminal.core.window_settings import DEFAULT_WINDOW_SETTINGS
    from terminal.memory import confirmations, system_commands

    monkeypatch.setattr(
        chat_context,
        "CHAT_CONTEXTS_DIR",
        tmp_path / "chat_contexts",
    )

    settings = copy.deepcopy(DEFAULT_WINDOW_SETTINGS)
    settings["response"] = {
        **settings["response"],
        "typing_enabled": False,
    }

    monkeypatch.setattr(
        gui,
        "load_window_settings",
        lambda: copy.deepcopy(settings),
    )
    monkeypatch.setattr(gui, "add_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        confirmations,
        "add_action",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        system_commands,
        "add_action",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(gui, "get_active_model", lambda: None)
    monkeypatch.setattr(
        gui,
        "get_current_model_id",
        lambda: gui.DEFAULT_MODEL_ID,
    )

    instance = gui.GiperionWindow()

    yield instance

    instance.window.deleteLater()
    qapp.processEvents()
