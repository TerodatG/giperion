# Giperion/terminal/ui/panels_side.py                                  v001
# Полоса модулей и боковые кнопки под аватаром.
# Последнее изменение: вынесено из panels_mixin.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from terminal.core.conference_catalog import (
    get_conference_members,
    get_mode,
    get_selected_mode_id,
)
from terminal.core.conference_roster import (
    MAX_CONFERENCE_MODELS,
    select_conference_models,
)
from terminal.core.model_registry import (
    get_current_model_id,
    get_model,
    load_conference_ids,
    set_conference_member,
)
from terminal.core.module_state import set_module
from terminal.ui.panels_data import (
    EMPTY_MODULE_BUTTONS,
    MODULE_INFO,
    MODULE_SLOTS,
)
from terminal.ui.widgets import (
    FuturisticGrip,
    ModuleButton,
    SideIconButton,
)


class SidePanelMixin:
    """Часть панелей окна."""

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

        for key in MODULE_SLOTS:
            if key == "empty":
                row.addWidget(
                    ModuleButton(
                        "empty",
                        "Свободный слот",
                        "",
                        container,
                    )
                )

                continue

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

    def _build_side_buttons(self, parent=None) -> QWidget:
        """Собирает плиту «Система» с кнопками-пиктограммами."""

        panel = parent or self.window.toolsPanel

        container = QWidget(panel)
        container.setObjectName("systemPanel")
        container.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(4)

        caption = QLabel("СИСТЕМА", container)
        caption.setObjectName("systemCaption")
        caption.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        row = QGridLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # Четыре кнопки в линию: 36 px + зазоры помещаются в плиту 198 px.
        def make_button(icon: str, tooltip: str) -> SideIconButton:
            """Создаёт кнопку плиты одного размера."""

            return SideIconButton(
                icon,
                tooltip,
                container,
                size=(36, 34),
            )

        self.skills_button = make_button("skills", "Умения")
        self.models_button = make_button("models", "Модель")
        self.workshop_button = make_button("workshop", "Мастерская")
        self.conference_button = make_button(
            "conference",
            "Вид сената",
        )
        self.personalities_button = make_button(
            "personalities",
            "Личностные матрицы",
        )
        self.settings_button = make_button("settings", "Настройки")
        self.update_button = make_button("update", "Обновление")
        self.performance_button = make_button(
            "performance",
            "Производительность",
        )
        self.drone_button = make_button("drone", "Дрон")

        buttons = (
            self.skills_button,
            self.models_button,
            self.workshop_button,
            self.conference_button,
            self.personalities_button,
            self.settings_button,
            self.update_button,
            self.performance_button,
            self.drone_button,
        )

        for index, button in enumerate(buttons):
            row.addWidget(button, index // 4, index % 4)

        self.skills_button.clicked.connect(
            self.open_skills_dialog
        )
        self.models_button.clicked.connect(
            self.open_models_dialog
        )
        self.workshop_button.clicked.connect(
            self.open_workshop_dialog
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
        self.update_button.clicked.connect(
            self.open_update_dialog
        )
        self.performance_button.clicked.connect(
            self.open_performance_dialog
        )
        self.drone_button.clicked.connect(
            self.open_pets_dialog
        )

        layout.addWidget(caption)
        layout.addLayout(row)
        layout.addStretch(1)

        # Размерный уголок — в нижнем правом углу плиты «Система».
        grip = FuturisticGrip(container)
        grip.setFixedSize(18, 18)

        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch(1)
        grip_row.addWidget(grip)

        layout.addLayout(grip_row)

        self.side_actions_panel = container
        self.system_panel = container

        return container

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

        note = {
            "voice": self._voice_toggle_note,
            "internet": self._internet_toggle_note,
            "conference": self._conference_toggle_note,
        }.get(key, self._models_toggle_note)(enabled)

        self.append_system(note)

    def _voice_toggle_note(self, enabled: bool) -> str:
        """Текст для голосового модуля."""

        if enabled:
            self._schedule_voice()

            return (
                "Голос включён. Иногда я буду комментировать "
                "происходящее, шутить и насвистывать."
            )

        self.voice_timer.stop()

        return "Голос выключен."

    def _internet_toggle_note(self, enabled: bool) -> str:
        """Текст для сетевого модуля."""

        if enabled:
            return (
                "Сетевой модуль включён. Спроси: "
                "«найди в интернете …»."
            )

        return "Сетевой модуль выключен. Поиск недоступен."

    def _models_toggle_note(self, enabled: bool) -> str:
        """Текст для помощи моделей."""

        if enabled:
            return (
                "Помощь моделей включена. Если ядро будет "
                "сомневаться, оно спросит внешнюю модель."
            )

        return "Помощь моделей выключена."

    def _conference_toggle_note(self, enabled: bool) -> str:
        """Текст для сената с составом и резервом."""

        added_name = ""
        pet_off = False

        if enabled and getattr(self, "attached_pet", None):
            self.detach_pet(announce=False)
            pet_off = True

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
            note = "Сенат выключен. В чате отвечает одна модель."
        elif mode is not None and mode["id"] != "council":
            note = (
                f"Сенат включён. Режим «{mode['name']}» "
                "пока не реализован; сейчас работает только "
                "«Параллельный совет»."
            )
        elif not members:
            note = (
                "Сенат включён, но участники не отмечены. "
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
                "Сенат включён. "
                f"Режим «{mode['name']}». Состав: {roster}."
            )

            if len(members) > MAX_CONFERENCE_MODELS:
                reserve = len(members) - MAX_CONFERENCE_MODELS
                note += f" В резерве по репутации: {reserve}."

            if added_name:
                note += (
                    f" Активная модель «{added_name}» "
                    "добавлена в сенат."
                )

        if pet_off:
            note += " Дрон откреплён: включён сенат."

        return note
