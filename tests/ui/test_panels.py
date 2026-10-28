# Giperion/tests/ui/test_panels.py                                   v001
# Панели, аватар, вложения, производительность и обновление.
# Последнее изменение: вынесено из test_gui_smoke.



def test_system_buttons_live_in_system_panel(window) -> None:
    """Системные кнопки стоят в плите «Система» под открытыми чатами."""

    assert window.chats_panel.objectName() == "chatsPanel"
    assert window.chats_panel.parent() is window.window.toolsPanel
    assert window.system_panel.objectName() == "systemPanel"
    assert window.system_panel.parent() is window.window.toolsPanel

    for button in (
        window.skills_button,
        window.models_button,
        window.workshop_button,
        window.conference_button,
        window.personalities_button,
        window.settings_button,
        window.help_button,
        window.performance_button,
        window.update_button,
        window.drone_button,
    ):
        assert button.parent() is window.system_panel

    from PySide6.QtWidgets import QGridLayout

    grid = window.system_panel.findChild(QGridLayout)

    assert grid is not None
    assert grid.columnCount() == 4
    assert window.skills_button.width() == 36


def test_files_module_button_is_empty_slot(window) -> None:
    """Кнопки «Файлы ПК» больше нет: её слот пустой."""

    from terminal.ui.widgets import ModuleButton

    kinds = [
        button.kind
        for button in window.modules_panel.findChildren(ModuleButton)
    ]

    assert "files" not in window.module_buttons
    assert kinds.count("empty") == 1
    assert len(kinds) == 6


def test_model_avatar_switches_main_screen(window, monkeypatch) -> None:
    """У активной модели на главном экране свой живой портрет."""

    from PySide6.QtGui import QPixmap

    from config import BASE_DIR
    from terminal.core.model_registry import get_model
    from terminal.ui import avatar_mixin

    model = get_model("deepseek-v4.1-flash-free")

    monkeypatch.setattr(
        avatar_mixin,
        "get_active_model",
        lambda: model,
    )

    window.apply_model_avatar()

    expected = QPixmap(str(BASE_DIR / model["avatar"]))

    assert not expected.isNull()
    assert window.avatar_caption.text() == "ОБРАЗ МОДЕЛИ"
    assert window.avatar_pixmap.size() == expected.size()

    # Анимация: пульс глаза, слой линий и падающие огоньки.
    assert window.avatar_animated is True
    assert window.avatar_timer.isActive()
    assert window.avatar_eye_mode == "pulse"
    assert len(window.avatar_eyes) == 1
    assert not window.avatar_lines.isNull()
    assert window.avatar_sparks

    before = window.avatar_sparks[0].y
    window._advance_sparks(1.0)

    assert window.avatar_sparks[0].y != before


def test_giperion_avatar_keeps_lid_animation(window, monkeypatch) -> None:
    """У Гипериона остаются веки и автопоиск двух глаз."""

    from terminal.core.model_registry import get_model
    from terminal.ui import avatar_mixin

    model = get_model("giperion")

    monkeypatch.setattr(
        avatar_mixin,
        "get_active_model",
        lambda: model,
    )

    window.apply_model_avatar()

    assert window.avatar_caption.text() == "ОБРАЗ ГИПЕРИОНА"
    assert window.avatar_eye_mode == "lid"
    assert len(window.avatar_eyes) == 2
    assert window.avatar_animated is True
    assert not window.avatar_sparks


def test_attachment_plus_opens_menu(window, monkeypatch) -> None:
    """«Плюс» открывает меню, а файл читается без модуля."""

    from terminal.ui import file_attachment_mixin
    from terminal.ui.widgets import AttachButton

    assert isinstance(window.attach_button, AttachButton)
    assert window.attach_button.toolTip() == "Добавить вложение"

    actions = [
        action.text()
        for action in window._attachment_menu().actions()
    ]

    assert actions[0] == "Загрузить файл"

    # Модуль «Файлы ПК» выключен, но загрузка всё равно работает.
    window.modules["files"] = False

    data = {
        "name": "note.txt",
        "text": "привет",
        "size": 12,
        "encoding": "utf-8",
        "full_length": 6,
        "truncated": False,
    }

    monkeypatch.setattr(
        file_attachment_mixin.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: ("note.txt", ""),
    )
    monkeypatch.setattr(
        file_attachment_mixin,
        "read_text_file",
        lambda path: data,
    )

    window.attach_text_file()

    assert "note.txt" in window.chat.toPlainText()
    assert "ФАЙЛ" in window.chat.toPlainText()


def test_performance_dialog_shows_live_metrics(
    window,
    monkeypatch,
) -> None:
    """Окно «Производительность» показывает нагрузку и умеет паузу."""

    from terminal.core.performance_monitor import (
        PerformanceSample,
        VolumeUsage,
    )
    from terminal.ui import performance_dialog as module

    class FakeMonitor:
        """Заглушка счётчиков: один и тот же снимок без системы."""

        def __init__(self) -> None:
            self.closed = False

        def sample(self) -> PerformanceSample:
            return PerformanceSample(
                cpu_percent=42.0,
                cpu_cores=[10.0, 74.0],
                cpu_frequency_mhz=4300.0,
                ram_total=16 * 1024**3,
                ram_available=8 * 1024**3,
                ram_percent=50.0,
                disk_percent=12.0,
                disk_read_bps=2048.0,
                disk_write_bps=1024.0,
                net_down_bps=125_000.0,
                net_up_bps=12_500.0,
                gpu_percent=6.0,
                gpu_memory_used=2 * 1024**3,
                gpu_memory_total=16 * 1024**3,
                volumes=[VolumeUsage("C:", 1000, 250)],
                uptime=3661.0,
                source="заглушка",
            )

        def close(self) -> None:
            self.closed = True

    fake = FakeMonitor()
    monkeypatch.setattr(module, "create_monitor", lambda: fake)

    window.open_performance_dialog()

    dialog = window.window._tool_windows["performance"]
    dialog._tick()

    assert dialog.cpu_card.value.text() == "42%"
    assert dialog.ram_card.value.text() == "50%"
    assert dialog.disk_card.value.text() == "12%"
    assert dialog.net_card.value.text() == "1,0 Мбит/с"
    assert dialog.gpu_card.value.text() == "6%"
    assert dialog.cpu_cores._loads == [10.0, 74.0]
    assert dialog.volumes._volumes[0].name == "C:"
    assert "16" in dialog.ram_card.detail.text()

    dialog.pause_button.setChecked(True)

    assert dialog._paused is True
    assert dialog.pause_button.text() == "Дальше"

    dialog.pause_button.setChecked(False)

    assert dialog._paused is False

    dialog.close()

    assert fake.closed is True


def test_update_dialog_checks_downloads_and_installs(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """Окно обновления: проверка, скачивание и установка патча."""

    import json
    import time
    import zipfile

    from PySide6.QtWidgets import QApplication

    from terminal.core import app_version, update_channel, update_service

    root = tmp_path / "project"
    root.mkdir()

    data = root / "data"
    data.mkdir()

    feed = data / "releases.json"
    state = data / "update_state.json"

    patch_source = root / "source.zip"

    with zipfile.ZipFile(patch_source, "w") as archive:
        archive.writestr("docs/release.md", "новая версия")

    feed.write_text(
        json.dumps(
            {
                "version": "v001",
                "channel": "stable",
                "releases": [
                    {
                        "version": "1.1.0",
                        "date": "2026-11-01",
                        "title": "Тестовый выпуск",
                        "notes": ["Новый пункт изменений"],
                        "patch": str(patch_source),
                    },
                    {
                        "version": "1.0.0",
                        "date": "2026-10-25",
                        "title": "Текущий выпуск",
                        "notes": ["Старый пункт изменений"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(update_service, "PROJECT_ROOT", root)
    monkeypatch.setattr(update_service, "UPDATES_DIR", root / "updates")
    monkeypatch.setattr(update_service, "FEED_FILE", feed)
    monkeypatch.setattr(app_version, "STATE_FILE", state)
    # Окно читает канал из переменной окружения: иначе полезет в сеть.
    monkeypatch.setenv(update_channel.FEED_ENV, str(feed))

    def wait_for_job(dialog, timeout: float = 5.0) -> None:
        """Ждёт, пока фоновая операция окна закончится."""

        deadline = time.monotonic() + timeout

        while dialog._job is not None and time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(0.02)

        assert dialog._job is None

    window.open_update_dialog()

    dialog = window.window._tool_windows["update"]

    # До проверки — сведения о текущем выпуске.
    assert "1.0.0" in dialog.log.toPlainText()
    assert "Старый пункт изменений" in dialog.log.toPlainText()
    assert not dialog.download_button.isEnabled()
    assert not dialog.update_button.isEnabled()

    # Проверка дополняет журнал новым выпуском и прокручивает к нему.
    dialog.check_button.click()
    wait_for_job(dialog)

    assert "1.1.0" in dialog.log.toPlainText()
    assert "Новый пункт изменений" in dialog.log.toPlainText()
    assert "НОВОЕ" in dialog.log.toPlainText()
    assert "Доступно обновление 1.1.0" in dialog.status_label.text()
    assert dialog.download_button.isEnabled()
    assert not dialog.update_button.isEnabled()
    assert dialog.log.verticalScrollBar().value() == 0

    # Скачивание кладёт патч в updates под именем с версией и датой.
    dialog.download_button.click()
    wait_for_job(dialog)

    assert dialog._patched is not None
    assert dialog._patched.path.name == (
        "giperion-1.1.0-2026-11-01.patch"
    )
    assert (
        "giperion-1.1.0-2026-11-01.patch"
        in dialog.status_label.text()
    )
    assert dialog.update_button.isEnabled()

    # Установка распаковывает патч и меняет версию.
    dialog.update_button.click()
    wait_for_job(dialog)

    assert app_version.current_version() == "1.1.0"
    assert "Установлено 1.1.0" in dialog.status_label.text()
    assert (
        root / "docs" / "release.md"
    ).read_text(encoding="utf-8") == "новая версия"
    assert not dialog.update_button.isEnabled()

    dialog.close()


def test_update_dialog_survives_missing_feed(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """Пропавший каталог выпусков показывается ошибкой, а не падением."""

    from terminal.core import app_version, update_channel, update_service

    missing = tmp_path / "no-such-feed.json"

    monkeypatch.setattr(update_service, "FEED_FILE", missing)
    monkeypatch.setenv(update_channel.FEED_ENV, str(missing))
    monkeypatch.setattr(
        app_version,
        "STATE_FILE",
        tmp_path / "update_state.json",
    )

    window.open_update_dialog()

    dialog = window.window._tool_windows["update"]

    assert "недоступен" in dialog.log.toPlainText()
    assert dialog.check_button.isEnabled()
    assert not dialog.download_button.isEnabled()
    assert not dialog.update_button.isEnabled()

    dialog.close()
