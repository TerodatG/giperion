# Giperion/gui.py                                                v042
# Оконный ИИ-собеседник Гиперион на PySide6.
# Последнее изменение: горячие клавиши из настроек при запуске.

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication

from config import BASE_DIR
from shared.action_log import add_action
from terminal.core.conference_catalog import get_conference_members
from terminal.core.model_catalog import (
    DEFAULT_MODEL_ID,
)
from terminal.core.model_settings import (
    get_active_model,
    get_current_model_id,
)
from terminal.core.module_state import set_modules
from terminal.core.pets import get_active_pet
from terminal.core.skins import load_skin_id
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
from terminal.ui.keybindings_mixin import KeybindingsMixin
from terminal.ui.model_controls_mixin import ModelControlsMixin
from terminal.ui.panels_mixin import PanelsMixin
from terminal.ui.performance_mixin import PerformanceMixin
from terminal.ui.pets_mixin import PetsMixin
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
from terminal.ui.update_mixin import UpdateMixin
from terminal.ui.window_chrome_mixin import WindowChromeMixin
from terminal.ui.window_style import build_window_style

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
    PetsMixin,
    SettingsMixin,
    PerformanceMixin,
    UpdateMixin,
    KeybindingsMixin,
    InputMixin,
    AnswerMixin,
):
    """Соединяет окно Qt с логикой консольного Гипериона."""

    def __init__(self) -> None:
        self._load_window()
        self._resolve_speaker()
        self._setup_timers()
        self._load_appearance()
        self._build_interface()
        self._announce_start()

    def _load_window(self) -> None:
        """Загружает .ui и собирает безрамочную оболочку."""

        loader = QUiLoader()
        self.window = loader.load(str(WINDOW_FILE))

        if self.window is None:
            raise RuntimeError(
                f"Не удалось загрузить окно: {WINDOW_FILE}"
            )

        self.window_settings = load_window_settings()

        # Скин интерфейса переживает перезапуск.
        self.skin_id = load_skin_id()

        self.window.setStyleSheet(build_window_style(self.skin_id))
        self._build_window_shell()

        self.chat = self.window.chatHistory
        self.input = self.window.messageInput
        self.button = self.window.sendButton
        self.personality_title = self.window.personalityTitle
        self.personality_title.setGeometry(19, 11, 250, 20)

    def _resolve_speaker(self) -> None:
        """Определяет, кто отвечает в чате: модель или дрон."""

        active_model = get_active_model()
        self.bot_name = (
            active_model["name"] if active_model else BOT_NAME
        )
        self.bot_nickname = (
            (active_model.get("nickname") or self.bot_name)
            if active_model
            else BOT_NICKNAME
        )

        self.attached_pet = get_active_pet()

        if self.attached_pet is not None:
            self.bot_name = self.attached_pet["name"]
            self.bot_nickname = (
                self.attached_pet.get("nickname")
                or self.attached_pet["name"]
            )

        self.update_input_placeholder()
        self.button.setCursor(Qt.ArrowCursor)

    def _setup_timers(self) -> None:
        """Таймеры ожидания, печати и голоса."""

        self.answering = False
        self.thinking_frame = 0

        self.thinking_timer = QTimer(self.window)
        self.thinking_timer.setInterval(THINKING_STEP_MS)
        self.thinking_timer.timeout.connect(self._animate_thinking)

        self.typing_state = None
        self.typing_timer = QTimer(self.window)
        self.typing_timer.setInterval(TYPING_STEP_MS)
        self.typing_timer.timeout.connect(self._type_tick)

        self.voice_timer = QTimer(self.window)
        self.voice_timer.setSingleShot(True)
        self.voice_timer.timeout.connect(self._voice_tick)

    def _load_appearance(self) -> None:
        """Шрифт, цвета, стили, модули и списки чатов."""

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
        self.colors = {
            **DEFAULT_COLORS,
            **dict(self.window_settings.get("colors", {})),
        }
        self.styles = {
            **DEFAULT_STYLES,
            **dict(self.window_settings.get("styles", {})),
        }
        self.font_sizes = {
            **DEFAULT_FONT_SIZES,
            **dict(self.window_settings.get("font_sizes", {})),
        }
        self.response_settings = {
            **DEFAULT_RESPONSE_SETTINGS,
            **dict(self.window_settings.get("response", {})),
        }
        self.modules = {
            **DEFAULT_MODULE_STATES,
            **dict(self.window_settings.get("modules", {})),
        }

        set_modules(self.modules)

        self.module_buttons = {}
        self.bot_messages = []
        self.user_messages = []
        self.chat_log = []
        self.chats = []
        self.active_chat_index = -1
        self.chat_sequence = 0
        self.chat_epoch = 0

    def _build_interface(self) -> None:
        """Панели, кнопки, чаты и связи сигналов."""

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
        self.install_shortcuts()
        self._reconcile_conference_state()

        if (
            self.attached_pet is not None
            and self.modules.get("conference")
        ):
            self._turn_off_conference()

        if self.modules["voice"]:
            self._schedule_voice()

    def _announce_start(self) -> None:
        """Пишет приветствие и состояние собеседника."""

        add_action("Гиперион запущен (окно)")

        self.append_system(
            "Гиперион запущен. Для системных команд используй формат: "
            "«Гиперион, система: команда»."
        )
        self.append_system("Для завершения работы напиши: выход.")
        self.update_core_panel()

        if self.attached_pet is not None:
            pet = self.attached_pet
            self.append_system(
                f"За терминалом закреплён дрон «{pet['name']}». "
                "Теперь он отвечает в чате."
            )
            self.append_bot(
                pet["greeting"],
                name=pet.get("nickname") or pet["name"],
                role="bot",
                with_copy=False,
            )
        elif self.modules.get("conference"):
            members = get_conference_members()
            names = ", ".join(model["name"] for model in members)
            self.append_system(
                "Сенат включён. Отвечают: "
                f"{names or 'участники не выбраны'}."
            )
        elif get_current_model_id() == DEFAULT_MODEL_ID:
            self.append_bot("Привет! Я Гиперион. О чём поговорим?")
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
