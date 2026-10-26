# Giperion/terminal/ui/panels_misc.py                                  v003
# Подписи, фон личности, «Система», голос, инструменты и размеры чатов.
# Последнее изменение: выбранный скин в сохранении настроек.

import random

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from shared.action_log import add_action
from terminal.core.system_info import format_bytes, get_system_info
from terminal.core.window_settings import save_window_settings
from terminal.ui.chat_list_widgets import ChatItemDelegate, ChatListWidget
from terminal.ui.panels_data import (
    VOICE_MAX_MS,
    VOICE_MIN_MS,
    VOICE_REMARKS,
)


class PanelsMiscMixin:
    """Часть панелей окна."""

    def _add_panel_captions(self) -> None:
        """Подписывает панели, как пульты станции."""

        # Для каждой панели: заголовок и растяжение её содержимого.
        captions = (
            (self.window.avatarPanel, "ОБРАЗ ГИПЕРИОНА", (1,)),
            (self.window.chatPanel, "ТЕРМИНАЛ СВЯЗИ", (4, 0)),
        )

        for panel, text, stretches in captions:
            layout = panel.layout()

            if layout is None:
                continue

            caption = QLabel(text, panel)
            caption.setObjectName("panelCaption")
            caption.setSizePolicy(
                QSizePolicy.Preferred,
                QSizePolicy.Fixed,
            )

            layout.insertWidget(0, caption)
            layout.setStretch(0, 0)

            if panel is self.window.avatarPanel:
                self.avatar_caption = caption

            # Заголовок не должен съедать место у содержимого панели.
            for offset, stretch in enumerate(stretches, start=1):
                layout.setStretch(offset, stretch)

    def _install_personality_backdrop(self) -> None:
        """Кладёт зелёный экран под параметры ИИ в общей стилистике чата."""

        panel = self.window.personalityPanel

        backdrop = QWidget(panel)
        backdrop.setObjectName("personalityBackdrop")
        backdrop.setAttribute(Qt.WA_StyledBackground, True)
        backdrop.lower()

        self.personality_backdrop = backdrop

        self._position_personality_backdrop()

    def _position_personality_backdrop(self) -> None:
        """Растягивает зелёный экран по внутренней части панели."""

        if not hasattr(self, "personality_backdrop"):
            return

        panel = self.window.personalityPanel

        self.personality_backdrop.setGeometry(
            10,
            10,
            max(0, panel.width() - 20),
            max(0, panel.height() - 20),
        )
        self.personality_backdrop.lower()

    def _build_system_page(self) -> QWidget:
        """Собирает закладку с параметрами компьютера."""

        info = get_system_info()

        page = QWidget(self.window.personalityPanel)
        page.setObjectName("systemPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(8)

        caption = QLabel("СИСТЕМА ПК", page)
        caption.setObjectName("executiveCaption")

        description = QLabel(
            "Среда, в которой запущен Гиперион.",
            page,
        )
        description.setObjectName("executiveHint")
        description.setWordWrap(True)

        scroll = QScrollArea(page)
        scroll.setObjectName("systemScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("systemContent")
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)

        memory = format_bytes(info["ram_total"])
        available = format_bytes(info["ram_available"])

        if available != "—":
            memory = f"{memory} (свободно {available})"

        disk = format_bytes(info["disk_total"])
        disk_free = format_bytes(info["disk_free"])

        if disk_free != "—":
            disk = f"{disk} (свободно {disk_free})"

        gpu = info["gpu"]

        if info["gpu_memory"]:
            gpu = f"{gpu} · {format_bytes(info['gpu_memory'])}"

        rows = (
            ("Компьютер", info["hostname"]),
            ("Операционная система", info["os"]),
            (
                "Процессор",
                f"{info['processor']} · потоков: {info['cpu_cores']}",
            ),
            ("Оперативная память", memory),
            ("Видеокарта", gpu),
            (
                "Жёсткий диск",
                f"{disk} · {info['disk_path']}",
            ),
            ("Python", info["python"]),
            (
                "PyTorch / CUDA",
                f"{info['torch']} · CUDA {info['cuda']}",
            ),
            ("Папка проекта", info["project"]),
        )

        for row_index, (title, value) in enumerate(rows):
            name = QLabel(f"{title}:", content)
            name.setObjectName("systemName")
            name.setWordWrap(True)
            name.setFixedWidth(118)

            text = QLabel(value, content)
            text.setObjectName("systemValue")
            text.setWordWrap(True)
            text.setFixedWidth(138)
            text.setTextInteractionFlags(Qt.TextSelectableByMouse)

            grid.addWidget(name, row_index, 0)
            grid.addWidget(text, row_index, 1)

        scroll.setWidget(content)

        layout.addWidget(caption)
        layout.addWidget(description)
        layout.addWidget(scroll, 1)

        return page

    def _schedule_voice(self) -> None:
        """Планирует следующую необязательную реплику."""

        if not self.modules.get("voice"):
            return

        self.voice_timer.start(
            random.randint(VOICE_MIN_MS, VOICE_MAX_MS)
        )

    def _voice_tick(self) -> None:
        """Иногда говорит сам с собой, если включён голосовой модуль."""

        if not self.modules.get("voice"):
            return

        visible = (
            self.window.isVisible()
            and not self.window.isMinimized()
        )

        if (
            visible
            and not self.answering
            and self.typing_state is None
        ):
            self.append_bot(
                random.choice(VOICE_REMARKS),
                with_copy=False,
            )

        self._schedule_voice()

    def _save_window_settings(self) -> None:
        """Сохраняет настройки окна на диск."""

        try:
            save_window_settings(
                {
                    "chat_font_family": self.chat_font_family,
                    "chat_font_size": self.chat_font_size,
                    "colors": dict(self.colors),
                    "styles": dict(self.styles),
                    "font_sizes": dict(self.font_sizes),
                    "response": dict(self.response_settings),
                    "modules": dict(self.modules),
                    "skin": getattr(self, "skin_id", "terminal"),
                }
            )
        except OSError as error:
            add_action(
                f"Не удалось сохранить настройки окна: {error}"
            )

    def _build_tools_panel(self) -> None:
        """Собирает правую колонку из двух плит: чаты и система."""

        panel = self.window.toolsPanel
        layout = panel.layout()

        if layout is None:
            return

        # Убираем старую текстовую кнопку и пустой распор из .ui.
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()

            if widget is self.window.settingsButton:
                widget.hide()
            elif widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # --- Верхняя плита: открытые чаты ---

        self.chats_panel = QWidget(panel)
        self.chats_panel.setObjectName("chatsPanel")
        self.chats_panel.setAttribute(Qt.WA_StyledBackground, True)

        chats_layout = QVBoxLayout(self.chats_panel)
        chats_layout.setContentsMargins(12, 12, 12, 12)
        chats_layout.setSpacing(6)

        caption = QLabel("ОТКРЫТЫЕ ЧАТЫ", self.chats_panel)
        caption.setObjectName("toolsCaption")
        caption.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.chat_list = ChatListWidget(self.chats_panel)
        self.chat_list.setObjectName("chatList")
        self.chat_list.setUniformItemSizes(True)
        self.chat_list.setSpacing(2)
        self.chat_list.setMouseTracking(True)
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.setItemDelegate(
            ChatItemDelegate(self.chat_list)
        )
        self.chat_list.currentRowChanged.connect(
            self._chat_row_changed
        )
        self.chat_list.chat_menu_requested.connect(
            self._chat_menu_from_row
        )
        self.chat_list.customContextMenuRequested.connect(
            self._chat_list_context_menu
        )
        self.chat_list.itemDoubleClicked.connect(
            self._chat_item_double_clicked
        )

        self.new_chat_button = QPushButton(
            "＋ Новый чат",
            self.chats_panel,
        )
        self.new_chat_button.setObjectName("newChatButton")
        self.new_chat_button.setCursor(Qt.ArrowCursor)
        self.new_chat_button.setMinimumHeight(36)
        self.new_chat_button.clicked.connect(self._new_chat_clicked)

        chats_layout.addWidget(caption)
        chats_layout.addWidget(self.chat_list, 1)
        chats_layout.addWidget(self.new_chat_button)

        # --- Нижняя плита: система ---

        system_panel = self._build_side_buttons(panel)

        layout.addWidget(self.chats_panel, 1)
        layout.addWidget(system_panel, 0)

        self.chat.resizeEvent = self._on_chat_resize
        QTimer.singleShot(0, self._sync_chats_plate_height)

    def _on_chat_resize(self, event) -> None:
        """Следит за высотой зелёного экрана чата."""

        QTextBrowser.resizeEvent(self.chat, event)
        self._sync_chats_plate_height()

    def _sync_chats_plate_height(self) -> None:
        """Ставит нижний край плиты «Открытые чаты» по низу чата."""

        if not hasattr(self, "chats_panel"):
            return

        try:
            panel_top = self.chats_panel.mapTo(
                self.window,
                QPoint(0, 0),
            ).y()
            chat_bottom = self.chat.mapTo(
                self.window,
                QPoint(0, self.chat.height()),
            ).y()
        except RuntimeError:
            # Окно уже закрывается: пересчитывать нечего.
            return

        height = chat_bottom - panel_top

        if height > 120:
            self.chats_panel.setFixedHeight(height)
