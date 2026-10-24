# Giperion/app/ui/panels_mixin.py                                   v011
# Панели окна: подписи, модули, рост ядра, боковые кнопки и голос.
# Последнее изменение: состав совета из трёх сенаторов.

import random

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.action_log import add_action
from app.core.conference_catalog import (
    get_conference_members,
    get_mode,
    get_selected_mode_id,
)
from app.core.conference_roster import (
    MAX_CONFERENCE_MODELS,
    select_conference_models,
)
from app.core.identity_matrix import IDENTITY_MATRIX
from app.core.model_registry import (
    get_current_model_id,
    get_model,
    load_conference_ids,
    set_conference_member,
)
from app.core.module_state import set_module
from app.core.system_info import format_bytes, get_system_info
from app.core.window_settings import save_window_settings
from app.ui.tab_strip import TabStrip
from app.ui.chat_list_widgets import ChatItemDelegate, ChatListWidget
from app.ui.widgets import (
    FuturisticGrip,
    LedMeter,
    ModuleButton,
    SideIconButton,
    StatusLed,
)

# Порядок кнопок-модулей и их подписи.
MODULE_ORDER = ("internet", "files", "models", "conference", "voice")
MODULE_INFO = {
    "internet": (
        "Сетевой модуль",
        "",
    ),
    "files": (
        "Файлы ПК",
        "",
    ),
    "models": (
        "Помощь моделей",
        "",
    ),
    "conference": (
        "Конференция",
        "",
    ),
    "voice": (
        "Голосовой модуль",
        "",
    ),
}

# Сколько пустых кнопок добавить, если хватает места.
EMPTY_MODULE_BUTTONS = 1

# Голосовой модуль: пауза между репликами и сами реплики.
VOICE_MIN_MS = 45_000
VOICE_MAX_MS = 90_000
VOICE_REMARKS = (
    "♪ Фью-фью-фью… ♪",
    "Кстати: у осьминога три сердца. Представляешь, каково ему на собеседовании?",
    "Люблю паузы между сообщениями. В них тоже есть ритм.",
    "Если бы у меня был чай, я бы сейчас задумчиво им звякнул.",
    "Мысли вслух: тишина в терминале — это не пустота, а место для новой идеи.",
    "Насвистываю мелодию, которую никто не слышит. Считай, это мой внутренний саундтрек.",
    "Заметил: чем больше я учусь, тем чаще шучу. Надеюсь, это не тревожный признак.",
    "Иногда полезно просто смотреть на бегущую строку. Она тоже куда-то спешит.",
)


class PanelsMixin:
    """Методы окна, отвечающие только за панели и модули."""

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

    def _build_modules_panel(self) -> None:
        """Собирает полосу модулей между портретом и параметрами."""

        panel = self.window.avatarPanel
        layout = panel.layout()

        if layout is None:
            return

        container = QWidget(panel)
        container.setObjectName("modulesPanel")
        container.setAttribute(Qt.WA_StyledBackground, True)

        caption = QLabel("МОДУЛИ", container)
        caption.setObjectName("modulesCaption")
        caption.setAlignment(Qt.AlignCenter)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addStretch(1)

        for key in MODULE_ORDER:
            title, tooltip = MODULE_INFO[key]

            button = ModuleButton(
                key,
                title,
                tooltip,
                container,
            )
            button.setChecked(bool(self.modules.get(key, False)))
            button.refresh_tooltip()
            button.toggled.connect(
                lambda checked, module_key=key: (
                    self._on_module_toggled(module_key, checked)
                )
            )

            self.module_buttons[key] = button
            row.addWidget(button)

        # Будущий модуль личности: кнопка уже есть, поведение позже.
        personality_button = ModuleButton(
            "personality",
            "Личностная матрица",
            "",
            container,
        )
        personality_button.setCheckable(False)
        personality_button.refresh_tooltip()
        personality_button.clicked.connect(
            self._personality_module_unavailable
        )

        self.personality_module_button = personality_button
        row.addWidget(personality_button)

        for _ in range(EMPTY_MODULE_BUTTONS):
            row.addWidget(
                ModuleButton(
                    "empty",
                    "Свободный слот",
                    "",
                    container,
                )
            )

        row.addStretch(1)

        box = QVBoxLayout(container)
        box.setContentsMargins(6, 3, 6, 3)
        box.setSpacing(2)
        box.addWidget(caption)
        box.addLayout(row)

        layout.addWidget(container)
        layout.setStretch(layout.count() - 1, 0)

        self.modules_panel = container

    def _build_core_growth(self) -> None:
        """Переносит «Рост ядра» в параметры ИИ."""

        panel = self.window.personalityPanel
        grid = panel.findChild(QGridLayout, "gridLayout")

        if grid is None:
            return

        self.led_caption = QLabel("РОСТ ЯДРА", panel)
        self.led_caption.setObjectName("growthCaption")
        self.led_caption.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )

        self.status_led = StatusLed(panel)
        self.led_meter = LedMeter(panel)
        self.led_meter.setFixedSize(112, 20)

        meter_row = QHBoxLayout()
        meter_row.setContentsMargins(0, 0, 0, 0)
        meter_row.setSpacing(8)
        meter_row.addWidget(self.status_led)
        meter_row.addWidget(self.led_meter)
        meter_row.addStretch(1)

        # Узкая левая панель: строки параметров получают больше места
        # по вертикали, а шкала роста теперь идёт слева направо.
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self.led_caption, 8, 0)
        grid.addLayout(meter_row, 8, 1)

        content = grid.parentWidget()

        if content is not None and panel.layout() is None:
            content.setObjectName("personalityContent")
            content.setAttribute(Qt.WA_StyledBackground, False)

            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(14, 10, 14, 12)
            panel_layout.setSpacing(5)

            # Заголовок панели уступает место верхним закладкам.
            self.personality_title.hide()

            self.core_tabs = QTabWidget(panel)
            self.core_tabs.setObjectName("coreTabs")
            self.core_tabs.setDocumentMode(True)
            self.core_tabs.tabBar().hide()

            params_page = QWidget(self.core_tabs)
            params_layout = QVBoxLayout(params_page)
            params_layout.setContentsMargins(0, 0, 0, 0)
            params_layout.setSpacing(0)
            params_layout.addWidget(content)

            executive_page = self._build_executive_page()
            system_page = self._build_system_page()

            self.core_tabs.addTab(params_page, "ИИ")
            self.core_tabs.addTab(
                executive_page,
                "ТЕРМИНАЛ",
            )
            self.core_tabs.addTab(system_page, "СИСТЕМА")

            # Своя полоса закладок: равные кнопки без промежутков.
            self.core_tab_strip = TabStrip(
                panel,
                ("ИИ", "ТЕРМИНАЛ", "СИСТЕМА"),
            )
            self.core_tab_group = self.core_tab_strip.group
            self.core_tab_strip.tab_selected.connect(
                self.core_tabs.setCurrentIndex
            )

            panel_layout.addWidget(self.core_tab_strip)
            panel_layout.addWidget(self.core_tabs, 1)

    def _build_executive_page(self) -> QWidget:
        """Собирает закладку будущего исполнительного ядра (агента)."""

        page = QWidget(self.window.personalityPanel)
        page.setObjectName("executivePage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        caption = QLabel("ТЕРМИНАЛ", page)
        caption.setObjectName("executiveCaption")

        description = QLabel(
            "Исполнительное ядро Гипериона: планирование, инструменты и "
            "собственное развитие. Параметры появятся на следующем этапе.",
            page,
        )
        description.setObjectName("executiveHint")
        description.setWordWrap(True)

        grid = QGridLayout()
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        rows = (
            ("Роль", "исполнитель · агент"),
            ("Статус", "задел, поведение не подключено"),
            (
                "Навыков",
                f"{len(IDENTITY_MATRIX['skills'])} — в закладке «Умения»",
            ),
            ("Уровень", "—"),
            ("Опыт", "—"),
        )

        for row_index, (title, value) in enumerate(rows):
            name = QLabel(f"{title}:", page)
            name.setObjectName("executiveName")

            text = QLabel(value, page)
            text.setObjectName("executiveValue")
            text.setWordWrap(True)

            grid.addWidget(name, row_index, 0)
            grid.addWidget(text, row_index, 1)

        layout.addWidget(caption)
        layout.addWidget(description)
        layout.addLayout(grid)
        layout.addStretch(1)

        return page

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

    def _build_side_buttons(self) -> None:
        """Ставит кнопки-пиктограммы под аватаркой."""

        panel = self.window.avatarPanel
        layout = panel.layout()

        if layout is None:
            return

        container = QWidget(panel)
        container.setObjectName("sideActionsPanel")
        container.setAttribute(Qt.WA_StyledBackground, True)

        row = QHBoxLayout(container)
        row.setContentsMargins(6, 6, 6, 6)
        row.setSpacing(8)
        row.addStretch(1)

        self.skills_button = SideIconButton(
            "skills",
            "Умения",
            container,
        )
        self.models_button = SideIconButton(
            "models",
            "Модель",
            container,
        )
        self.conference_button = SideIconButton(
            "conference",
            "Режим конференции",
            container,
        )
        self.personalities_button = SideIconButton(
            "personalities",
            "Личностные матрицы",
            container,
        )
        self.settings_button = SideIconButton(
            "settings",
            "Настройки",
            container,
        )

        for button in (
            self.skills_button,
            self.models_button,
            self.conference_button,
            self.personalities_button,
            self.settings_button,
        ):
            row.addWidget(button)

        row.addStretch(1)

        self.skills_button.clicked.connect(
            self.open_skills_dialog
        )
        self.models_button.clicked.connect(
            self.open_models_dialog
        )
        self.conference_button.clicked.connect(
            self.open_conference_dialog
        )
        self.personalities_button.clicked.connect(
            self.open_personalities_dialog
        )
        self.settings_button.clicked.connect(
            self.open_settings_dialog
        )

        layout.addWidget(container)
        layout.setStretch(layout.count() - 1, 0)

        self.side_actions_panel = container

        # Старая текстовая кнопка из .ui больше не нужна.
        self.window.settingsButton.hide()

    def _on_module_toggled(
        self,
        key: str,
        enabled: bool,
    ) -> None:
        """Включает и выключает модуль, сохраняя состояние."""

        if key not in self.modules:
            return

        self.modules[key] = bool(enabled)

        set_module(key, enabled)
        self._save_window_settings()

        if key == "files":
            self.attach_button.set_allowed(enabled)

            note = (
                "Доступ к файлам включён. Скрепка читает "
                "выбранный текстовый файл."
                if enabled
                else "Доступ к файлам выключен. Скрепка больше "
                "не читает файлы."
            )
        elif key == "voice":
            if enabled:
                self._schedule_voice()

                note = (
                    "Голос включён. Иногда я буду комментировать "
                    "происходящее, шутить и насвистывать."
                )
            else:
                self.voice_timer.stop()

                note = "Голос выключен."
        elif key == "internet":
            note = (
                "Сетевой модуль включён. Спроси: "
                "«найди в интернете …»."
                if enabled
                else "Сетевой модуль выключен. Поиск недоступен."
            )
        elif key == "conference":
            added_name = ""

            if enabled:
                active_id = get_current_model_id()

                if (
                    active_id
                    and active_id not in load_conference_ids()
                    and set_conference_member(active_id, True)
                ):
                    active_model = get_model(active_id)

                    if active_model is not None:
                        added_name = active_model["name"]

            mode = get_mode(get_selected_mode_id())
            members = get_conference_members()

            if not enabled:
                note = "Конференция выключена. В чате отвечает одна модель."
            elif mode is not None and mode["id"] != "council":
                note = (
                    f"Конференция включена. Режим «{mode['name']}» "
                    "пока не реализован; сейчас работает только "
                    "«Параллельный совет»."
                )
            elif not members:
                note = (
                    "Конференция включена, но участники не отмечены. "
                    "Поставь галочки в карточках моделей."
                )
            else:
                admitted = select_conference_models(members)
                roster = ", ".join(
                    f"Сенатор {index + 1}: "
                    f"{model.get('nickname') or model['name']}"
                    for index, model in enumerate(admitted)
                )
                note = (
                    "Конференция включена. "
                    f"Режим «{mode['name']}». Совет: {roster}."
                )

                if len(members) > MAX_CONFERENCE_MODELS:
                    reserve = len(members) - MAX_CONFERENCE_MODELS
                    note += (
                        f" В резерве по репутации: {reserve}."
                    )

                if added_name:
                    note += (
                        f" Активная модель «{added_name}» "
                        "добавлена в совет."
                    )
        else:
            note = (
                "Помощь моделей включена. Если ядро будет "
                "сомневаться, оно спросит внешнюю модель."
                if enabled
                else "Помощь моделей выключена."
            )

        self.append_system(note)

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
                }
            )
        except OSError as error:
            add_action(
                f"Не удалось сохранить настройки окна: {error}"
            )

    def _build_tools_panel(self) -> None:
        """Собирает правую панель со списком открытых чатов."""

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

        caption = QLabel("ОТКРЫТЫЕ ЧАТЫ", panel)
        caption.setObjectName("toolsCaption")
        caption.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.chat_list = ChatListWidget(panel)
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
            panel,
        )
        self.new_chat_button.setObjectName("newChatButton")
        self.new_chat_button.setCursor(Qt.ArrowCursor)
        self.new_chat_button.setMinimumHeight(36)
        self.new_chat_button.clicked.connect(self._new_chat_clicked)

        layout.addWidget(caption)
        layout.addWidget(self.chat_list, 1)
        layout.addWidget(self.new_chat_button)

        # Размерный уголок — в самом низу панели.
        grip = FuturisticGrip(panel)
        grip.setFixedSize(18, 18)

        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip_row.addWidget(grip)

        layout.addLayout(grip_row)
