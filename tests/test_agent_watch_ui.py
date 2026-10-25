# Giperion/tests/test_agent_watch_ui.py                               v001
# Окно наблюдателя: запуск/остановка и обработка изменений.

import pytest

from terminal.core.agent.watch import Changes


@pytest.fixture(scope="module")
def qapp():
    """Приложение Qt для окна наблюдателя."""

    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()

    if application is None:
        application = QApplication([])

    return application


class FakeWatcher:
    """Подмена реального потока опроса."""

    def __init__(self, *args, **kwargs) -> None:
        self.started = False

    def start(self, on_change=None, on_error=None, initial=True) -> None:
        self.on_change = on_change
        self.started = True

    def stop(self) -> None:
        self.started = False


@pytest.fixture()
def dialog(qapp, monkeypatch):
    from terminal.ui import watch_dialog

    monkeypatch.setattr(watch_dialog, "Watcher", FakeWatcher)
    monkeypatch.setattr(
        watch_dialog,
        "save_settings",
        lambda settings: None,
    )

    window = watch_dialog.WatchDialog(None)

    yield window

    window.close()


def test_dialog_starts_and_stops(dialog) -> None:
    """Кнопка включает и выключает наблюдение."""

    assert dialog.start_button.text() == "Начать наблюдение"
    assert dialog.watcher is None

    dialog._toggle()

    assert isinstance(dialog.watcher, FakeWatcher)
    assert dialog.start_button.text() == "Остановить"
    assert "Наблюдаю" in dialog.status_label.text()

    dialog._toggle()

    assert dialog.watcher is None
    assert dialog.start_button.text() == "Начать наблюдение"


def test_change_is_logged_without_autorun(dialog) -> None:
    """Без авто-запуска изменения просто попадают в журнал."""

    dialog.auto_check.setChecked(False)
    dialog._settings_value = dialog._settings()

    dialog._handle(Changes(added=["new.py"], modified=["a.py"]))

    text = dialog.log.toPlainText()

    assert "изменения (2)" in text
    assert "new.py" in text
    assert "a.py" in text
    assert "Авто-запуск выключен" in dialog.status_label.text()
    assert dialog.job is None


def test_autorun_without_model_is_reported(dialog, monkeypatch) -> None:
    """Если модели нет, окно объясняет это и не падает."""

    dialog.auto_check.setChecked(True)
    dialog._settings_value = dialog._settings()
    monkeypatch.setattr(
        dialog,
        "_brain",
        lambda: (None, ""),
    )

    dialog._handle(Changes(modified=["a.py"]))

    assert "Нет модели" in dialog.status_label.text()
    assert dialog.job is None


def test_change_pending_is_processed_by_poll(dialog) -> None:
    """Изменения из потока обрабатываются в потоке окна."""

    dialog.auto_check.setChecked(False)
    dialog._settings_value = dialog._settings()
    dialog._pending = Changes(added=["from-thread.py"])

    dialog._poll()

    assert "from-thread.py" in dialog.log.toPlainText()
    assert dialog._pending is None
