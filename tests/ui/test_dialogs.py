# Giperion/tests/ui/test_dialogs.py                                  v001
# Диалоги мастерской, агента и модулей.
# Последнее изменение: вынесено из test_gui_smoke.



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
    """«Мастерская» открывается и предлагает шесть инструментов."""

    from PySide6.QtWidgets import QPushButton, QSizeGrip

    window.open_workshop_dialog()

    dialog = window.window._tool_windows["workshop"]

    assert dialog.windowTitle() == "Мастерская"

    actions = [
        button.text()
        for button in dialog.findChildren(QPushButton)
        if button.objectName() == "workshopAction"
    ]

    assert actions == [
        "Агент",
        "Модель",
        "Личности",
        "Умения",
        "Журнал",
    ]
    assert window.settings_button.toolTip() == "Настройки"
    assert dialog.findChild(QSizeGrip, "workshopSizeGrip") is not None
    assert dialog.findChild(QPushButton, "titleButton") is not None
    title_buttons = dialog.findChildren(QPushButton, "titleButton")

    assert len(title_buttons) == 3
    assert any(
        button.toolTip() == "Справка по окну"
        for button in title_buttons
    )

    dialog.close()


def test_main_title_bar_has_help(window) -> None:
    """На планке главного окна есть кнопка справки."""

    from PySide6.QtWidgets import QPushButton

    buttons = window.title_bar.findChildren(
        QPushButton,
        "titleButton",
    )

    assert any(
        button.toolTip() == "Справка по окну"
        for button in buttons
    )


def test_help_button_opens_help_window(window) -> None:
    """Кнопка «Справка» на системной панели открывает окно справки."""

    from PySide6.QtWidgets import QTextBrowser

    window.open_help_dialog()

    dialog = window.window._tool_windows["help"]

    assert dialog.windowTitle() == "Справка"

    view = dialog.findChild(QTextBrowser, "helpView")

    assert view is not None
    assert "СИСТЕМНЫЕ КОМАНДЫ" in view.toPlainText()

    dialog.close()


def test_workshop_has_terminal_and_panels(window) -> None:
    """В мастерской есть три окна вывода, ввод и плиты по бокам."""

    from PySide6.QtWidgets import (
        QApplication,
        QPlainTextEdit,
        QPushButton,
        QTextBrowser,
        QWidget,
    )

    window.open_workshop_dialog()
    QApplication.processEvents()

    dialog = window.window._tool_windows["workshop"]
    answers = dialog.findChild(QTextBrowser, "workshopAnswers")
    system = dialog.findChild(QPlainTextEdit, "systemLog")
    tools = dialog.findChild(QPlainTextEdit, "agentTrace")
    message = dialog.findChild(QPlainTextEdit, "workshopInput")

    assert answers is not None
    assert system is not None
    assert tools is not None
    assert message is not None
    assert message.height() >= message.fontMetrics().lineSpacing() * 3
    assert answers.size() == system.size()
    assert dialog.findChild(QWidget, "workshopPictureSlot") is not None
    assert dialog.findChild(QWidget, "chatsPanel") is not None
    assert dialog.findChild(QWidget, "systemPanel") is not None

    actions = dialog.findChildren(QPushButton, "workshopAction")

    assert len(actions) == 5

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
