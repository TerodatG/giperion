# Giperion/tests/ui/test_settings.py                                 v001
# Настройки, «О нас», шрифты и ответы.
# Последнее изменение: вынесено из test_gui_smoke.



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
