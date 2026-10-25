# Giperion/gui.py                                                v037
# Оконный ИИ-собеседник Гиперион на PySide6.
# Последнее изменение: правая колонка из двух плит.

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication

from shared.action_log import add_action
from terminal.core.conference_catalog import get_conference_members
from terminal.core.model_registry import (
    DEFAULT_MODEL_ID,
    get_active_model,
    get_current_model_id,
)
from terminal.core.module_state import set_modules
from terminal.core.window_settings import (
    DEFAULT_FONT_SIZES,
    DEFAULT_MODULE_STATES,
    DEFAULT_RESPONSE_SETTINGS,
    DEFAULT_STYLES,
    load_window_settings,
)
from terminal.ui.answer_mixin import AnswerMixin
from terminal.ui.avatar_mixin import AvatarMixin
from terminal.ui.chat_sessions_mixin import ChatSessionsMixin
from terminal.ui.dashboard_mixin import DashboardMixin
from terminal.ui.file_attachment_mixin import FileAttachmentMixin
from terminal.ui.input_mixin import InputMixin
from terminal.ui.model_controls_mixin import ModelControlsMixin
from terminal.ui.panels_mixin import PanelsMixin
from terminal.ui.settings_mixin import SettingsMixin
from terminal.ui.theme import (
    BOT_NAME,
    BOT_NICKNAME,
    DEFAULT_CHAT_FONT_FAMILY,
    DEFAULT_CHAT_FONT_SIZE,
    DEFAULT_COLORS,
    THINKING_STEP_MS,
    TYPING_STEP_MS,
)
from terminal.ui.transcript_mixin import TranscriptMixin
from terminal.ui.window_chrome_mixin import WindowChromeMixin
from terminal.ui.window_style import WINDOW_STYLE
from config import BASE_DIR

WINDOW_FILE = BASE_DIR / "main_window.ui"


class GiperionWindow(
    AvatarMixin,
    TranscriptMixin,
    ChatSessionsMixin,
    PanelsMixin,
    WindowChromeMixin,
    FileAttachmentMixin,
    DashboardMixin,
    ModelControlsMixin,
    SettingsMixin,
    InputMixin,
    AnswerMixin,
):
    """Соединяет окно Qt с логикой консольного Гипериона."""

    def __init__(self) -> None:
        loader = QUiLoader()

        self.window = loader.load(str(WINDOW_FILE))

        if self.window is None:
            raise RuntimeError(
                f"Не удалось загрузить окно: {WINDOW_FILE}"
            )

        # Настройки окна переживают перезапуск.
        self.window_settings = load_window_settings()

        # Собственная футуристическая шкура вместо рамки Windows.
        self.window.setStyleSheet(WINDOW_STYLE)
        self._build_window_shell()

        self.chat = self.window.chatHistory
        self.input = self.window.messageInput
        self.button = self.window.sendButton
        self.personality_title = self.window.personalityTitle

        # Надпись «Параметры ИИ» сдвинута вправо на пару символов.
        self.personality_title.setGeometry(19, 11, 250, 20)

        # Имя того, кто отвечает в чате: Гиперион или внешняя модель.
        # В терминале связи показывается короткий ник, в карточке — имя.
        active_model = get_active_model()
        self.bot_name = (
            active_model["name"] if active_model else BOT_NAME
        )
        self.bot_nickname = (
            (active_model.get("nickname") or self.bot_name)
            if active_model
            else BOT_NICKNAME
        )
        self.update_input_placeholder()

        # У кнопок — обычная стрелка, а не курсор растягивания окна.
        self.button.setCursor(Qt.ArrowCursor)

        # Ожидание ответа и анимация индикатора «обрабатываю запрос…».
        self.answering = False
        self.thinking_frame = 0

        self.thinking_timer = QTimer(self.window)
        self.thinking_timer.setInterval(THINKING_STEP_MS)
        self.thinking_timer.timeout.connect(self._animate_thinking)

        # Эмуляция печати: состояние одной печатающейся реплики.
        self.typing_state = None
        self.typing_timer = QTimer(self.window)
        self.typing_timer.setInterval(TYPING_STEP_MS)
        self.typing_timer.timeout.connect(self._type_tick)

        # Голосовой модуль: необязательные реплики по таймеру.
        self.voice_timer = QTimer(self.window)
        self.voice_timer.setSingleShot(True)
        self.voice_timer.timeout.connect(self._voice_tick)

        # Гарнитура и размер шрифта истории чата.
        self.chat_font_family = str(
            self.window_settings.get(
                "chat_font_family",
                DEFAULT_CHAT_FONT_FAMILY,
            )
        )
        self.chat_font_size = int(
            self.window_settings.get(
                "chat_font_size",
                DEFAULT_CHAT_FONT_SIZE,
            )
        )

        # Цвета текста (меняются в настройках).
        self.colors = {
            **DEFAULT_COLORS,
            **dict(self.window_settings.get("colors", {})),
        }

        # Виды шрифта для групп текста.
        self.styles = {
            **DEFAULT_STYLES,
            **dict(self.window_settings.get("styles", {})),
        }

        # Свой размер шрифта у групп текста (0 — как у всего чата).
        self.font_sizes = {
            **DEFAULT_FONT_SIZES,
            **dict(self.window_settings.get("font_sizes", {})),
        }

        # Настройки печати и задержки, а также состояния модулей.
        self.response_settings = {
            **DEFAULT_RESPONSE_SETTINGS,
            **dict(
                self.window_settings.get("response", {})
            ),
        }
        self.modules = {
            **DEFAULT_MODULE_STATES,
            **dict(
                self.window_settings.get("modules", {})
            ),
        }

        # Модули влияют не только на окно, но и на логику ответов.
        set_modules(self.modules)

        # Кнопки модулей: ключ → кнопка.
        self.module_buttons = {}

        # Тексты ответов Гипериона для ссылок «копировать».
        self.bot_messages = []

        # Тексты сообщений пользователя для ссылок «копировать»/«править».
        self.user_messages = []

        # Журнал чата для перерисовки при смене цветов.
        # Элементы: («user»/«bot»/«system», текст) или («level», уровень, ранг).
        self.chat_log = []

        # Независимые открытые чаты. Каждый хранит свой журнал и списки
        # копирования; переключение не смешивает диалоги.
        self.chats = []
        self.active_chat_index = -1
        self.chat_sequence = 0
        self.chat_epoch = 0

        self._add_panel_captions()
        self._show_avatar()
        self._install_personality_backdrop()
        self._build_core_growth()
        self._build_modules_panel()
        self._add_attachment_button()
        self.clear_button = self._add_clear_button()
        self._apply_chat_font()
        self._build_system_log()

        self.button.clicked.connect(self.send_message)
        self.clear_button.clicked.connect(self.clear_chat)
        self._build_tools_panel()
        self._create_chat(announce=False)
        self.chat.anchorClicked.connect(self._on_anchor_clicked)
        self.chat.setOpenLinks(False)
        self._build_context_menus()
        self._reconcile_conference_state()

        if self.modules["voice"]:
            self._schedule_voice()

        add_action("Гиперион запущен (окно)")

        self.append_system(
            "Гиперион запущен. Для системных команд используй формат: "
            "«Гиперион, система: команда»."
        )
        self.append_system(
            "Для завершения работы напиши: выход."
        )

        self.update_core_panel()

        if self.modules.get("conference"):
            members = get_conference_members()
            names = ", ".join(
                model["name"] for model in members
            )
            self.append_system(
                "Сенат включён. Отвечают: "
                f"{names or 'участники не выбраны'}."
            )
        elif get_current_model_id() == DEFAULT_MODEL_ID:
            self.append_bot(
                "Привет! Я Гиперион. О чём поговорим?"
            )
        else:
            self.append_system(
                f"Активна модель «{self.bot_name}». "
                "Она отвечает в чате."
            )

        self.input.setFocus()

    # --- Каркас безрамочного окна ---



    # --- Оформление окна ---




    # --- Настройки ---




    # --- Вывод сообщений ---


    # --- Панель ядра ---


    # --- Обработка ввода ---



def main() -> None:
    """Запускает оконный диалог Гипериона."""

    application = QApplication(sys.argv)

    window = GiperionWindow()
    window.window.show()
    window.center_on_screen()

    # Панель уже получила настоящий размер — подгоняем образ.
    window.update_avatar_pixmap()

    sys.exit(application.exec())


if __name__ == "__main__":
    main()
