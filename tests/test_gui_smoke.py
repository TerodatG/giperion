# Giperion/tests/test_gui_smoke.py                                 v030
# Дымовые проверки окна без показа на экране (offscreen).
# Последнее изменение: шапка без подписи и числа агента.

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


def test_window_starts_with_one_chat(window) -> None:
    """Окно поднимается и открывает первый терминал связи."""

    assert window.bot_name == "Гиперион"
    assert len(window.chats) == 1
    assert window.active_chat_index == 0
    assert window.chat_list.count() == 1
    assert window.input.placeholderText()


def test_window_shows_messages_and_updates_panel(window) -> None:
    """Сообщения попадают в журнал и в панель ядра."""

    log_size = len(window.chat_log)

    window.append_user("проверка связи")
    window.append_bot("ответ на проверку")

    assert len(window.chat_log) == log_size + 2
    assert "проверка связи" in window.chat.toPlainText()
    assert "ответ на проверку" in window.chat.toPlainText()

    window.update_core_panel()


def test_window_keeps_chats_separate(window) -> None:
    """Переключение чатов не смешивает журналы."""

    window.append_user("первый чат")
    window._create_chat(announce=False)
    window.append_user("второй чат")

    window._activate_chat(0)

    first_text = window.chat.toPlainText()

    assert "первый чат" in first_text
    assert "второй чат" not in first_text

    window._activate_chat(1)

    second_text = window.chat.toPlainText()

    assert "второй чат" in second_text
    assert "первый чат" not in second_text


def test_empty_system_command_explains_format(window) -> None:
    """Пустая системная команда подсказывает правильный формат."""

    window._process_system_command("")

    assert "Например" in window.system_log.toPlainText()


def test_system_messages_go_to_separate_field(window) -> None:
    """Системные сообщения не попадают в терминал связи."""

    window.append_system("проверка системного поля")

    assert (
        "проверка системного поля"
        in window.system_log.toPlainText()
    )
    assert (
        "проверка системного поля"
        not in window.chat.toPlainText()
    )


def test_pending_action_belongs_to_one_chat(window) -> None:
    """Ожидающее подтверждение не переходит в другой чат."""

    from terminal.core import pending_state

    window._create_chat(announce=False)
    pending_state.set_pending_action("clear_conversations")

    assert pending_state.has_pending_action()

    window._activate_chat(0)

    assert not pending_state.has_pending_action()

    window._activate_chat(1)

    assert pending_state.has_pending_action()


def test_confirmation_goes_through_system_path(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """«Подтверждаю» выполняется как системная команда, не как реплика."""

    from terminal.core import pending_state
    from terminal.memory import memory

    monkeypatch.setattr(
        memory,
        "UNKNOWN_MESSAGES_FILE",
        tmp_path / "unknown_messages.json",
    )

    pending_state.set_pending_action("clear_unknown_messages")

    window.input.setPlainText("подтверждаю")
    window.send_message()

    assert (
        "Список непонятых фраз очищен"
        in window.system_log.toPlainText()
    )
    assert not pending_state.has_pending_action()


def test_model_activation_updates_speaker(
    window,
    monkeypatch,
) -> None:
    """Переключение модели меняет имя отвечающего, но не чистит чат."""

    from terminal.core.model_registry import get_model
    from terminal.ui import model_controls_mixin

    monkeypatch.setattr(
        model_controls_mixin,
        "add_action",
        lambda *args, **kwargs: 0,
    )

    model = get_model("deepseek-v4.1-flash-free")
    old_name = window.chats[0]["name"]

    window.append_user("старая история")
    window.activate_model(model)

    assert window.bot_name == model["name"]
    assert window.bot_nickname == model["nickname"]
    assert window.chats[0]["name"] == old_name
    assert any(
        entry[0] == "user" and entry[1] == "старая история"
        for entry in window.chat_log
    )
    assert "очищен" not in window.chat_log[-1][1].lower()


def test_model_activation_disables_conference(
    window,
    monkeypatch,
) -> None:
    """Активация модели выключает сенат, чтобы отвечала она."""

    from terminal.core.model_registry import get_model
    from terminal.ui import model_controls_mixin

    monkeypatch.setattr(
        model_controls_mixin,
        "add_action",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        model_controls_mixin,
        "set_module",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        window,
        "_save_window_settings",
        lambda: None,
    )

    window.modules["conference"] = True
    button = window.module_buttons["conference"]
    button.blockSignals(True)
    button.setChecked(True)
    button.blockSignals(False)

    model = get_model("deepseek-v4.1-flash-free")
    window.activate_model(model)

    assert window.modules["conference"] is False
    assert not button.isChecked()
    assert window.bot_name == model["name"]
    assert "Активна модель" in window.system_log.toPlainText()
    assert "Сенат выключен" in window.system_log.toPlainText()


def test_startup_reconciles_stale_conference(
    window,
    monkeypatch,
) -> None:
    """Старое состояние «совет включён, модель вне его» исправляется."""

    from terminal.ui import model_controls_mixin

    monkeypatch.setattr(
        model_controls_mixin,
        "get_current_model_id",
        lambda: "go-beam-free",
    )
    monkeypatch.setattr(
        model_controls_mixin,
        "load_conference_ids",
        lambda: ["go-deepseek-v4.1-flash", "giperion"],
    )
    monkeypatch.setattr(
        model_controls_mixin,
        "set_module",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        window,
        "_save_window_settings",
        lambda: None,
    )

    window.modules["conference"] = True
    button = window.module_buttons["conference"]
    button.blockSignals(True)
    button.setChecked(True)
    button.blockSignals(False)

    window._reconcile_conference_state()

    assert window.modules["conference"] is False
    assert not button.isChecked()
    assert "не входила в сенат" in window.system_log.toPlainText()


def test_new_chat_uses_active_model_name(
    window,
    monkeypatch,
) -> None:
    """Имя нового чата берётся из активной модели."""

    from terminal.core.model_registry import get_model
    from terminal.ui import chat_sessions_mixin

    model = get_model("deepseek-v4.1-flash-free")

    monkeypatch.setattr(
        chat_sessions_mixin,
        "get_active_model",
        lambda: model,
    )

    window._create_chat(announce=False)

    assert window.chats[-1]["name"].startswith(model["name"])


def test_chat_context_is_hidden_and_complete(window) -> None:
    """Выжимка хранит реплики, но не выводится в чат."""

    from terminal.core import chat_context

    window.append_user("первый вопрос")
    window.append_bot("первый ответ")
    window._update_chat_context()

    session = window.chats[0]
    text = chat_context.read_chat_context(
        session["context_id"]
    )

    assert "Пользователь: первый вопрос" in text
    assert "Giperion: первый ответ" in text
    assert "СИСТЕМА" not in text
    assert "Контекст чата" not in window.chat.toPlainText()


def test_context_excludes_current_question(window) -> None:
    """Текущая реплика не дублируется в истории запроса."""

    window.append_user("первый вопрос")
    window.append_bot("первый ответ")
    window.append_user("второй вопрос")

    context = window._context_for_model(
        exclude_last_user=True
    )

    assert "первый вопрос" in context
    assert "первый ответ" in context
    assert "второй вопрос" not in context


def test_conference_participants_need_council_mode(
    window,
    monkeypatch,
) -> None:
    """Параллельный совет работает только при включённом модуле и режиме."""

    from terminal.ui import answer_mixin

    monkeypatch.setattr(
        answer_mixin,
        "is_module_enabled",
        lambda key: key == "conference",
    )
    monkeypatch.setattr(
        answer_mixin,
        "get_selected_mode_id",
        lambda: "council",
    )
    monkeypatch.setattr(
        answer_mixin,
        "load_conference_ids",
        lambda: ["giperion", "deepseek-v4.1-flash-free"],
    )

    participants = window._conference_participants()

    assert [model["id"] for model in participants] == [
        "giperion",
        "deepseek-v4.1-flash-free",
    ]

    monkeypatch.setattr(
        answer_mixin,
        "get_selected_mode_id",
        lambda: "debate",
    )

    assert window._conference_participants() == []


def test_extracted_dialogs_construct(
    window,
    monkeypatch,
) -> None:
    """Вынесенные окна собираются без показа и не теряют импорты."""

    from terminal.ui import dialogs_base
    from terminal.ui.conference_dialog import show_conference_dialog
    from terminal.ui.models_dialog import show_models_dialog
    from terminal.ui.personalities_dialog import show_personalities_dialog
    from terminal.ui.pets_dialog import show_pets_dialog
    from terminal.ui.skills_dialog import show_skills_dialog

    monkeypatch.setattr(
        dialogs_base.SkinDialog,
        "exec",
        lambda self: 0,
    )

    show_models_dialog(window.window)
    show_personalities_dialog(window.window)
    show_skills_dialog(window.window)
    show_pets_dialog(window.window)
    show_conference_dialog(window.window)
    window.open_settings_dialog()

    pets_window = window.window._tool_windows.get("pets")

    if pets_window is not None:
        pets_window.close()


def test_core_tabs_are_present(window) -> None:
    """В панели ядра три закладки, заголовок уступил им место."""

    from PySide6.QtWidgets import QLabel, QPushButton

    labels = [
        window.core_tabs.tabText(index)
        for index in range(window.core_tabs.count())
    ]
    buttons = [
        button.text()
        for button in window.core_tab_strip.findChildren(QPushButton)
    ]
    system_texts = {
        label.text()
        for label in window.core_tabs.widget(2).findChildren(QLabel)
    }

    assert labels == [
        "ИИ",
        "ТЕРМИНАЛ",
        "СИСТЕМА",
    ]
    assert buttons == labels
    assert window.personality_title.isHidden()
    assert any("Процессор:" in text for text in system_texts)

    window.core_tab_group.button(2).click()
    assert window.core_tabs.currentIndex() == 2
    assert window.core_tab_group.button(2).isChecked()


def test_module_tooltips_have_no_extra_comments(window) -> None:
    """У голоса, «плюса» и личности в подсказке только название."""

    voice = window.module_buttons["voice"]

    assert voice.toolTip() == "Голосовой модуль"
    assert "files" not in window.module_buttons
    assert (
        window.personality_module_button.toolTip()
        == "Личностная матрица"
    )
    assert window.skills_button.toolTip() == "Умения"
    assert window.models_button.toolTip() == "Модель"
    assert window.workshop_button.toolTip() == "Мастерская"
    assert (
        window.conference_button.toolTip()
        == "Вид сената"
    )
    assert (
        window.personalities_button.toolTip()
        == "Личностные матрицы"
    )
    assert window.drone_button.toolTip() == "Дрон"
    assert (
        window.performance_button.toolTip()
        == "Производительность"
    )
    assert window.update_button.toolTip() == "Обновление"


def test_tool_windows_do_not_block_each_other(window) -> None:
    """Окна терминала немодальные: можно открыть несколько сразу."""

    from PySide6.QtWidgets import QFrame

    window.open_models_dialog()
    window.open_settings_dialog()

    windows = window.window._tool_windows

    assert {"models", "settings"} <= set(windows)

    for key in ("models", "settings"):
        dialog = windows[key]

        assert dialog.isVisible()
        assert dialog.isModal() is False

    settings = windows["settings"]
    settings.stack.setCurrentIndex(2)

    assert settings.findChildren(QFrame, "paramsPlate")

    for dialog in list(windows.values()):
        dialog.close()


def test_workshop_dialog_lists_tools(window) -> None:
    """«Мастерская» открывается и предлагает пять инструментов."""

    from PySide6.QtWidgets import QPushButton

    window.open_workshop_dialog()

    dialog = window.window._tool_windows["workshop"]

    assert dialog.windowTitle() == "Мастерская"

    actions = [
        button.text()
        for button in dialog.findChildren(QPushButton)
        if button.objectName() == "workshopAction"
    ]

    assert actions == [
        "Открыть агента",
        "Открыть «Модель»",
        "Открыть личности",
        "Открыть умения",
        "Добавить модель",
        "Открыть журнал",
    ]
    assert window.settings_button.toolTip() == "Настройки"

    dialog.close()


def test_agent_dialog_opens_with_approval(window) -> None:
    """Окно агента открывается; панель подтверждения спрятана."""

    window.open_agent_dialog()

    dialog = window.window._tool_windows["agent"]

    assert dialog.windowTitle() == "Агент"
    assert dialog.trace.isReadOnly()
    assert dialog.stop_button.isEnabled() is False
    assert dialog.approval_frame.isHidden()
    assert dialog.task_input.toPlainText() == ""
    assert dialog.worktree_checkbox.text().startswith("Отдельная ветка")
    assert dialog.new_task_button.text() == "Новая задача"
    assert dialog.policy_combo.currentData() in (
        "read",
        "confirm",
        "trust",
    )
    assert dialog.merge_button.isHidden()
    assert dialog.remove_button.isHidden()

    dialog.close()


def test_agent_provider_dialog_opens(window) -> None:
    """Кнопка «Провайдер…» открывает настройки провайдера."""

    from PySide6.QtWidgets import QLineEdit

    window.open_agent_dialog()

    windows = window.window._tool_windows
    dialog = windows["agent"]

    dialog.provider_button.click()

    provider = dialog._tool_windows["agent-provider"]

    assert provider.windowTitle() == "Провайдер агента"
    assert provider.base_input is not None
    assert (
        provider.key_input.echoMode()
        == QLineEdit.EchoMode.Password
    )

    provider.close()
    dialog.close()


def test_agent_runs_dialog_opens(window) -> None:
    """Журнал агента открывается из окна."""

    window.open_agent_runs_dialog()

    dialog = window.window._tool_windows["agent-runs"]

    assert dialog.windowTitle() == "Журнал агента"
    assert dialog.view.isReadOnly()

    dialog.close()


def test_agent_tasks_dialog_lists_states(window, monkeypatch) -> None:
    """Окно задач показывает сохранённые задачи."""

    from terminal.ui import agent_tasks_dialog

    state = {
        "id": "20261025-test",
        "task": "проверить задачи",
        "status": "running",
        "updated_at": "2026-10-25T12:00:00",
        "steps": [{"index": 1, "kind": "tool", "title": "read_file"}],
        "history": [{"tool": "read_file", "args": {}, "ok": True, "text": "x"}],
    }

    monkeypatch.setattr(
        agent_tasks_dialog,
        "list_states",
        lambda: [state],
    )

    agent_tasks_dialog.show_agent_tasks_dialog(window.window)

    dialog = window.window._tool_windows["agent-tasks"]

    assert dialog.windowTitle() == "Задачи агента"
    assert dialog.view.count() == 1

    dialog.view.setCurrentRow(0)
    assert "проверить задачи" in dialog.details.text()

    dialog.close()


def test_agent_dialog_prefills_resume(window) -> None:
    """Окно агента заполняется сохранённой задачей."""

    from terminal.ui.agent_dialog import AgentDialog

    state = {
        "id": "20261025-test",
        "task": "продолжить меня",
        "policy": "confirm",
        "root": str(window.window.property("dummy") or ""),
        "steps": [
            {"index": 1, "kind": "tool", "title": "read_file", "detail": "x"}
        ],
        "history": [],
    }

    dialog = AgentDialog(window.window, resume=state)

    assert dialog.task_input.toPlainText() == "продолжить меня"
    assert "read_file" in dialog.trace.toPlainText()
    assert dialog.status_label.text().startswith("Продолжение")

    dialog.close()


def test_agent_new_task_opens_second_window(window) -> None:
    """«Новая задача» открывает второе окно, не закрывая первое."""

    window.open_agent_dialog()

    windows = window.window._tool_windows
    first = windows["agent"]

    first._open_new_task()

    agent_keys = [
        key for key in windows if key.startswith("agent")
    ]

    assert len(agent_keys) >= 2
    assert windows[agent_keys[0]].isVisible()

    for key in agent_keys:
        windows[key].close()


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

    from terminal.core import app_version, update_service

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

    from terminal.core import app_version, update_service

    monkeypatch.setattr(
        update_service,
        "FEED_FILE",
        tmp_path / "no-such-feed.json",
    )
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


def test_model_groups_switch_disables_models(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """Галочки групп выключают модели, сенат и компаньонов."""

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QLabel,
        QListWidget,
        QPushButton,
        QTabBar,
    )

    from terminal.core import model_files, model_settings
    from terminal.core.model_catalog import CONFERENCE_GROUP

    monkeypatch.setattr(
        model_files,
        "SETTINGS_FILE",
        tmp_path / "model_settings.json",
    )

    go_id = "go-deepseek-v4.1-flash"

    assert model_settings.set_conference_member(go_id, True)

    window.open_models_dialog()

    dialog = window.window._tool_windows["models"]

    boxes = {
        box.text(): box
        for box in dialog.findChildren(QCheckBox)
    }

    assert boxes["Бесплатные модели"].isChecked()
    assert boxes["Модели Go"].isChecked()

    tabs = dialog.findChild(QTabBar)
    view = dialog.findChild(QListWidget, "modelsView")

    def row_ids() -> list[str]:
        """Идентификаторы строк текущей закладки."""

        return [
            view.item(index).data(Qt.UserRole)
            for index in range(view.count())
        ]

    senate = next(
        index
        for index in range(tabs.count())
        if tabs.tabData(index) == CONFERENCE_GROUP
    )
    tabs.setCurrentIndex(senate)
    QApplication.processEvents()

    assert go_id in row_ids()

    boxes["Модели Go"].setChecked(False)
    QApplication.processEvents()

    assert go_id not in row_ids()
    assert go_id not in model_settings.load_conference_ids()

    other = next(
        index
        for index in range(tabs.count())
        if tabs.tabData(index) == "other"
    )
    tabs.setCurrentIndex(other)
    QApplication.processEvents()

    for index in range(view.count()):
        if view.item(index).data(Qt.UserRole) == go_id:
            view.setCurrentRow(index)

            break

    QApplication.processEvents()

    status = dialog.findChild(QLabel, "modelStatus")
    activate = dialog.findChild(QPushButton, "activateButton")

    assert "недоступна" in status.text()
    assert "Модели Go" in status.text()
    assert activate.isEnabled() is False
    assert "· недоступна" in view.currentItem().text()

    boxes["Модели Go"].setChecked(True)
    QApplication.processEvents()

    assert go_id in model_settings.load_conference_ids()

    dialog.close()


def test_pet_nickname_can_be_changed_in_dialog(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """В окне «Дроны» кличка меняется кнопкой."""

    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from terminal.core import pets
    from terminal.ui import pets_dialog

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )
    monkeypatch.setattr(
        pets_dialog,
        "_ask_nickname",
        lambda parent, pet: "Бублик",
    )

    window.open_pets_dialog()

    dialog = window.window._tool_windows["pets"]

    texts = [label.text() for label in dialog.findChildren(QLabel)]

    # В карточке нет дубля вида, а кличка по умолчанию не задана.
    assert texts.count("Кибер паук") == 1
    assert any("КЛИЧКА: не задана" in text for text in texts)

    button = next(
        item
        for item in dialog.findChildren(QPushButton)
        if item.text() == "✎ Переименовать"
    )

    button.click()
    QApplication.processEvents()

    loaded = {pet["id"]: pet for pet in pets.load_pets()}

    assert loaded["cyber-spider"]["nickname"] == "Бублик"
    assert loaded["cyber-spider"]["name"] == "Кибер паук"

    texts = [label.text() for label in dialog.findChildren(QLabel)]

    assert any("КЛИЧКА: Бублик" in text for text in texts)

    dialog.close()


def test_own_model_can_be_deleted(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """В закладке «Свои» модель удаляется из каталога."""

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QListWidget,
        QPushButton,
        QTabBar,
    )

    from terminal.core import model_files, model_registry
    from terminal.ui import dialogs_base

    monkeypatch.setattr(
        model_files,
        "CUSTOM_MODELS_FILE",
        tmp_path / "custom_models.json",
    )
    monkeypatch.setattr(
        model_files,
        "SETTINGS_FILE",
        tmp_path / "model_settings.json",
    )
    monkeypatch.setattr(
        dialogs_base.ConfirmDialog,
        "exec",
        lambda self: QDialog.Accepted,
    )

    model = model_registry.add_custom_model("Своя", "Local")

    assert model is not None

    window.open_models_dialog()

    dialog = window.window._tool_windows["models"]

    tabs = dialog.findChild(QTabBar)
    own = next(
        index
        for index in range(tabs.count())
        if tabs.tabData(index) == "own"
    )
    tabs.setCurrentIndex(own)
    QApplication.processEvents()

    view = dialog.findChild(QListWidget, "modelsView")
    row = next(
        index
        for index in range(view.count())
        if view.item(index).data(Qt.UserRole) == model["id"]
    )
    view.setCurrentRow(row)
    QApplication.processEvents()

    delete = next(
        button
        for button in dialog.findChildren(QPushButton)
        if button.text() == "− Удалить модель"
    )

    assert delete.isVisible()
    assert delete.isEnabled()

    delete.click()
    QApplication.processEvents()

    ids = [
        item["id"] for item in model_registry.load_models()
    ]

    assert model["id"] not in ids

    dialog.close()


def test_custom_drone_can_be_deleted(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """В окне «Дроны» своего дрона можно удалить."""

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QListWidget,
        QPushButton,
    )

    from terminal.core import pets
    from terminal.ui import dialogs_base

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )
    monkeypatch.setattr(
        dialogs_base.ConfirmDialog,
        "exec",
        lambda self: QDialog.Accepted,
    )

    custom = pets.add_custom_pet("Шарик", "spider")

    assert custom is not None

    window.open_pets_dialog()

    dialog = window.window._tool_windows["pets"]

    delete = next(
        button
        for button in dialog.findChildren(QPushButton)
        if button.text() == "− Удалить дрона"
    )

    # По умолчанию выбран базовый дрон — удалять его нельзя.
    assert delete.isEnabled() is False

    view = dialog.findChild(QListWidget, "modelsView")

    for row in range(view.count()):
        if view.item(row).data(Qt.UserRole) == custom["id"]:
            view.setCurrentRow(row)

            break

    QApplication.processEvents()

    assert delete.isEnabled() is True

    delete.click()
    QApplication.processEvents()

    assert pets.get_pet(custom["id"]) is None

    dialog.close()


def test_add_model_dialog_uses_skin(qapp, monkeypatch) -> None:
    """Окно «Своя модель» одето в общую шкуру."""

    from PySide6.QtWidgets import QDialog

    from terminal.ui.add_model_dialog import show_add_model_dialog
    from terminal.ui.dialogs_base import SkinDialog

    captured = {}

    def fake_exec(self):
        captured["dialog"] = self

        return QDialog.Rejected

    monkeypatch.setattr(SkinDialog, "exec", fake_exec)

    assert show_add_model_dialog(None) is None
    assert isinstance(captured["dialog"], SkinDialog)
    assert captured["dialog"].windowTitle() == "Своя модель"
    assert captured["dialog"].title_bar is not None


def test_nickname_dialog_returns_new_value(qapp, monkeypatch) -> None:
    """Окно клички отдаёт введённое имя и подставляет текущее."""

    from PySide6.QtWidgets import QDialog, QLineEdit

    from terminal.ui import pets_dialog
    from terminal.ui.dialogs_base import SkinDialog

    seen = {}

    def fake_exec(self):
        field = self.findChild(QLineEdit)

        seen["before"] = field.text()
        field.setText("Бублик")

        return QDialog.Accepted

    monkeypatch.setattr(SkinDialog, "exec", fake_exec)

    result = pets_dialog._ask_nickname(
        None,
        {"name": "Кибер паук", "nickname": "Пёс"},
    )

    assert seen["before"] == "Пёс"
    assert result == "Бублик"


def test_about_page_has_project_sections(window) -> None:
    """«О нас»: программа, команда, принципы и обратная связь."""

    from PySide6.QtWidgets import QLabel

    from terminal.core.app_version import current_version

    window.open_settings_dialog()

    dialog = window.window._tool_windows["settings"]
    dialog.stack.setCurrentIndex(2)

    texts = "\n".join(
        label.text()
        for label in dialog.stack.widget(2).findChildren(QLabel)
    )

    assert "О ПРОГРАММЕ" in texts
    assert "КОМАНДА" in texts
    assert "ПРИНЦИПЫ" in texts
    assert "ОБРАТНАЯ СВЯЗЬ" in texts
    assert "Terodat" in texts
    assert current_version() in texts

    dialog.close()


def test_header_shows_only_title(window) -> None:
    """На планке заголовка только эмблема и название."""

    from PySide6.QtWidgets import QLabel

    texts = [
        label.text()
        for label in window.title_bar.findChildren(QLabel)
    ]

    assert texts == ["◈", "ГИПЕРИОН"]
    assert not hasattr(window, "title_status")


def test_terminal_tab_shows_agent_numbers(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """Закладка «Терминал» показывает числовые показатели агента."""

    import json

    from terminal.core.agent import runs

    path = tmp_path / "agent_runs.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "created_at": "2026-10-25T10:00:00",
                        "steps": 3,
                        "approvals": 2,
                        "duration_s": 12.0,
                        "files": ["a.py"],
                        "tokens": 120,
                    }
                ),
                json.dumps(
                    {
                        "created_at": "2026-10-25T11:30:00",
                        "steps": 5,
                        "duration_s": 18.0,
                        "files": ["a.py", "b.py"],
                        "tokens": 80,
                        "error": "boom",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runs, "RUNS_FILE", path)

    window.update_executive_panel()

    assert window.executive_values["runs"].text() == "2"
    assert window.executive_values["ok"].text() == "1"
    assert window.executive_values["success"].text() == "50 %"
    assert window.executive_values["steps"].text() == "8"
    assert window.executive_values["files"].text() == "2"
    assert window.executive_values["approvals"].text() == "2"
    assert window.executive_values["duration"].text() == "30 с"
    assert window.executive_values["average"].text() == "15 с"
    assert window.executive_values["tokens"].text() == "200"
    assert window.executive_values["cost"].text() == "—"
    assert window.executive_level.text() == "УРОВЕНЬ 1"
    assert "25.10.2026 11:30" in window.executive_footer.text()


def test_pet_attachment_changes_responder(
    window,
    monkeypatch,
) -> None:
    """Закреплённый дрон становится отвечающим в чате."""

    from terminal.ui import pets_mixin

    pet = {
        "id": "cyber-spider",
        "name": "Кибер паук",
        "nickname": "Кибер паук",
        "greeting": "Писк!",
        "self_description": "Я Кибер паук.",
    }

    monkeypatch.setattr(
        pets_mixin,
        "get_active_pet",
        lambda: pet,
    )
    monkeypatch.setattr(
        pets_mixin,
        "set_active_pet_id",
        lambda *args, **kwargs: True,
    )

    window._pets_changed()

    assert window.attached_pet == pet
    assert window.bot_name == "Кибер паук"
    assert window.bot_nickname == "Кибер паук"
    assert window.input.placeholderText() == "Напиши Кибер паук…"

    monkeypatch.setattr(
        pets_mixin,
        "get_active_pet",
        lambda: None,
    )
    monkeypatch.setattr(
        pets_mixin,
        "get_active_model",
        lambda: None,
    )

    window._pets_changed()

    assert window.attached_pet is None
    assert window.bot_name == "Гиперион"


def test_chats_plate_bottom_matches_chat(window) -> None:
    """Нижний край плиты «Открытые чаты» совпадает с низом чата."""

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    window.window.resize(1080, 760)
    window.window.show()
    QApplication.processEvents()
    window._sync_chats_plate_height()
    QApplication.processEvents()

    plate_bottom = window.chats_panel.mapTo(
        window.window,
        QPoint(0, window.chats_panel.height()),
    ).y()
    chat_bottom = window.chat.mapTo(
        window.window,
        QPoint(0, window.chat.height()),
    ).y()

    assert plate_bottom == chat_bottom


def test_close_dialog_uses_green_screen(window, monkeypatch) -> None:
    """Надпись закрытия стоит на зелёном экране внутри плиты."""

    from PySide6.QtWidgets import QLabel, QWidget

    from terminal.ui import dialogs_base

    captured = {}

    def fake_exec(self):
        captured["screen"] = self.findChild(
            QLabel,
            "closeScreen",
        )
        captured["plate"] = self.findChild(
            QWidget,
            "closePlate",
        )

        return 0

    monkeypatch.setattr(
        dialogs_base.SkinDialog,
        "exec",
        fake_exec,
    )

    window._confirm_window_close()

    assert captured["screen"].text() == "Закрыть Терминал?"
    assert captured["plate"] is not None


def test_model_error_goes_to_system_field(window) -> None:
    """Ошибка внешней модели не попадает в терминал связи."""

    class FailedJob:
        """Неудачный ответ активной модели."""

        done = True
        error = None
        model_error = True
        answer = (
            "Модель «DeepSeek»: бесплатный лимит исчерпан. "
            "Подключи провайдера или подписку OpenCode Go."
        )
        error_reason = "Free usage limit reached"
        model_id = "deepseek"
        role = "bot"

    log_size = len(window.chat_log)

    window._set_answering(True)
    window._poll_answer(
        FailedJob(),
        "привет",
        1,
        "Гиперион",
        window.chat_epoch,
    )

    assert "лимит" in window.system_log.toPlainText()
    assert "лимит" not in window.chat.toPlainText()
    assert not window.answering
    assert not any(
        entry[0] == "bot"
        for entry in window.chat_log[log_size:]
    )


def test_conference_falls_back_to_local_core(
    window,
    monkeypatch,
) -> None:
    """Если все участники ошиблись, отвечает локальный Гиперион."""

    from terminal.core.conference import ConferenceReply
    from terminal.ui import answer_mixin

    saved = []

    class FailedJob:
        """Все участники вернули ошибку лимита."""

        done = True
        error = None
        replies = [
            ConferenceReply(
                model_id="deepseek",
                name="DeepSeek",
                text="Модель «DeepSeek»: бесплатный лимит исчерпан.",
                save_to_history=False,
                error=True,
            )
        ]

    monkeypatch.setattr(
        answer_mixin,
        "get_response",
        lambda text: ("локальный ответ", True),
    )
    monkeypatch.setattr(
        answer_mixin,
        "add_message",
        lambda *args, **kwargs: saved.append((args, kwargs)),
    )

    window._set_answering(True)
    window._poll_conference(
        FailedJob(),
        "привет",
        1,
        window.chat_epoch,
    )

    terminal = window.chat.toPlainText()

    assert "локальный ответ" in terminal
    assert "воздержался от ответа" in terminal
    assert "лимит" in window.system_log.toPlainText()
    assert "лимит" not in terminal
    assert not window.answering
    assert any(args[0] == "assistant" for args, _ in saved)


def test_external_font_group_has_size_and_color(window) -> None:
    """У группы внешних моделей свой цвет, размер и стиль."""

    from terminal.ui.theme import EXTERNAL_COLOR

    window.chat_font_size = 11
    window.font_sizes = {**window.font_sizes, "external": 15}
    window.styles = {**window.styles, "external": "italic"}

    text_format = window._typing_format("external")

    assert text_format.fontPointSize() == 15
    assert text_format.foreground().color().name() == EXTERNAL_COLOR
    assert text_format.fontItalic()
    assert "font-size:15pt" in window._text_style("external")


def test_senator_font_groups_are_used(window) -> None:
    """Ответы сенаторов рисуются их собственными группами шрифта."""

    from PySide6.QtGui import QFont

    from terminal.ui.theme import SENATOR_COLORS

    window.chat_font_size = 11
    window.font_sizes = {
        **window.font_sizes,
        "senator1": 13,
    }
    window.styles = {**window.styles, "senator1": "bold"}

    text_format = window._typing_format("senator1")

    assert text_format.fontPointSize() == 13
    assert (
        text_format.foreground().color().name()
        == SENATOR_COLORS["senator1"]
    )
    assert text_format.fontWeight() == QFont.Bold
    assert window._speaker_color("senator1") == (
        SENATOR_COLORS["senator1"]
    )
