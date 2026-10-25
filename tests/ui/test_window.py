# Giperion/tests/ui/test_window.py                                   v001
# Окно: старт, чаты, система, модели и сенат.
# Последнее изменение: вынесено из test_gui_smoke.



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
