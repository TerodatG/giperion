# Giperion/terminal/ui/models/dialog.py                                v001
# Окно «Модель»: закладки, карточка, активация и списки участия.
# Последнее изменение: show_models_dialog разобран на классы.

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from terminal.core.model_registry import (
    DEFAULT_MODEL_ID,
    get_model,
    remove_custom_model,
    set_companion,
    set_conference_member,
    set_current_model_id,
)
from terminal.core.model_settings import (
    set_model_group_enabled,
)
from terminal.ui.add_model_dialog import show_add_model_dialog
from terminal.ui.dialogs_base import (
    ConfirmDialog,
    SkinDialog,
    show_tool_window,
)
from terminal.ui.model_params_dialog import show_model_params_dialog
from terminal.ui.models.card import ModelCard
from terminal.ui.models.list_panel import ModelListPanel
from terminal.ui.models.state import ModelsState


class ModelsDialog(SkinDialog):
    """Окно выбора модели и управления списками."""

    def __init__(
        self,
        parent,
        state: ModelsState,
        on_activate=None,
    ) -> None:
        super().__init__(
            parent,
            "Модель",
            min_width=1000,
            min_height=720,
        )

        self.state = state
        self.on_activate = on_activate

        layout = self.body_layout

        title = QLabel("МОДЕЛИ", self)
        title.setObjectName("dialogTitle")

        subtitle = QLabel(
            "Выбери модель и нажми «Активировать». Карточка показывает "
            "сильные стороны, функции, лимиты токенов и репутацию. Галочка "
            "«Компаньон» отмечает модель, а закладка «Компаньоны» "
            "собирает отмеченные модели.",
            self,
        )
        subtitle.setObjectName("dialogHint")
        subtitle.setWordWrap(True)

        groups_row = self._build_groups_row()

        body = QHBoxLayout()
        body.setSpacing(12)

        self.panel = ModelListPanel(self)
        self.card = ModelCard(self)

        scroll = QScrollArea(self)
        scroll.setObjectName("cardScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(self.card)

        card_frame = QWidget(self)
        card_frame.setObjectName("modelScreenFrame")

        card_frame_layout = QVBoxLayout(card_frame)
        card_frame_layout.setContentsMargins(6, 6, 6, 6)
        card_frame_layout.setSpacing(0)
        card_frame_layout.addWidget(scroll)

        body.addWidget(self.panel, 1)
        body.addWidget(card_frame, 1)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        self.activate_button = QPushButton("Активировать", self)
        self.activate_button.setObjectName("activateButton")
        self.activate_button.setCursor(Qt.ArrowCursor)
        self.activate_button.setMinimumHeight(38)
        self.activate_button.setMinimumWidth(170)

        close_box = QDialogButtonBox(QDialogButtonBox.Ok, self)
        close_box.button(QDialogButtonBox.Ok).setText("Закрыть")
        close_box.accepted.connect(self.accept)

        buttons_row.addWidget(self.activate_button)
        buttons_row.addStretch(1)
        buttons_row.addWidget(close_box)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(groups_row)
        layout.addLayout(body, 1)
        layout.addLayout(buttons_row)

        self._connect_signals()

        current_model = self.state.find(self.state.current)
        start_group = current_model["group"] if current_model else "popular"

        self.panel.set_group(start_group)
        self._refresh_list()

        # Первый расчёт до показа окна использует ещё не применённые
        # метрики QSS: без этого первая строка наезжает на соседнюю.
        QTimer.singleShot(0, self.panel.relayout)

    def _build_groups_row(self) -> QHBoxLayout:
        """Две галочки групп и пояснение к ним."""

        self.free_checkbox = QCheckBox("Бесплатные модели", self)
        self.free_checkbox.setObjectName("modelGroupCheck")
        self.free_checkbox.setCursor(Qt.ArrowCursor)
        self.free_checkbox.setChecked(self.state.groups["free"])
        self.free_checkbox.setToolTip(
            "Модели OpenCode без подписки. Снятая галочка выключает их."
        )

        self.go_checkbox = QCheckBox("Модели Go", self)
        self.go_checkbox.setObjectName("modelGroupCheck")
        self.go_checkbox.setCursor(Qt.ArrowCursor)
        self.go_checkbox.setChecked(self.state.groups["go"])
        self.go_checkbox.setToolTip(
            "Модели подписки OpenCode Go. Снятая галочка выключает их."
        )

        hint = QLabel(
            "Выключенная группа не работает: модели нельзя активировать, "
            "они исчезают из сената и компаньонов.",
            self,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        row.addWidget(self.free_checkbox)
        row.addWidget(self.go_checkbox)
        row.addWidget(hint, 1)

        return row

    def _connect_signals(self) -> None:
        """Связывает панели, карточку и кнопки."""

        self.panel.group_changed.connect(
            lambda index: self._refresh_list()
        )
        self.panel.selection_changed.connect(self._show_card)
        self.panel.add_requested.connect(self._add_own_model)
        self.panel.delete_requested.connect(self._delete_own_model)

        self.card.params_requested.connect(self._open_params)
        self.card.companion_toggled.connect(self._toggle_companion)
        self.card.conference_toggled.connect(self._toggle_conference)
        self.card.site_requested.connect(self._open_site)
        self.card.api_requested.connect(self._connect_api)

        self.activate_button.clicked.connect(self._activate)

        self.free_checkbox.toggled.connect(
            lambda checked: self._toggle_group("free", checked)
        )
        self.go_checkbox.toggled.connect(
            lambda checked: self._toggle_group("go", checked)
        )

    def _selected_model(self) -> dict | None:
        """Модель, выбранная в списке."""

        model_id = self.panel.selected_id()

        if model_id is None:
            return None

        return self.state.find(model_id)

    def _refresh_list(self, keep_id: str | None = None) -> None:
        """Перерисовывает список текущей закладки и карточку."""

        models = self.state.visible(self.panel.group)

        self.panel.refresh(
            models,
            current=self.state.current,
            companions=self.state.companions,
            conference=self.state.conference,
            usable=self.state.model_usable,
            keep_id=keep_id,
        )
        self._show_card()

    def _show_card(self) -> None:
        """Показывает выбранную модель и настраивает кнопки окна."""

        model = self._selected_model()
        active = model is not None and model["id"] == self.state.current
        enabled = self.state.model_enabled(model)
        usable = self.state.model_usable(model)

        self.card.show_model(
            model,
            current=self.state.current,
            companions=self.state.companions,
            conference=self.state.conference,
            enabled=enabled,
            usable=usable,
        )

        self.activate_button.setEnabled(
            model is not None and not active and usable
        )
        self.panel.set_delete_enabled(
            model is not None and model["group"] == "own"
        )

    def _activate(self) -> None:
        """Активирует выбранную модель, не закрывая окно."""

        model = self._selected_model()

        if model is None or model["id"] == self.state.current:
            return

        if not self.state.model_usable(model):
            return

        if not set_current_model_id(model["id"]):
            return

        self.state.current = model["id"]

        self._refresh_list()

        if self.on_activate is not None:
            self.on_activate(model)

    def _add_own_model(self) -> None:
        """Добавляет свою модель и показывает её в списке."""

        model = show_add_model_dialog(self)

        if model is None:
            return

        self.state.reload_models()
        self.panel.set_group("own")
        self._refresh_list()
        self.panel.select_id(model["id"])
        self._show_card()

    def _delete_own_model(self) -> None:
        """Удаляет свою модель из каталога."""

        model = self._selected_model()

        if model is None or model["group"] != "own":
            return

        confirm = ConfirmDialog(
            self,
            "Удалить модель",
            f"Удалить «{model['name']}» из своих моделей? "
            "Запись исчезнет из каталога и из закреплённых списков.",
            "Удалить",
        )

        if confirm.exec() != QDialog.Accepted:
            return

        model_id = model["id"]

        # Сначала убираем из списков, пока модель ещё есть в каталоге.
        set_companion(model_id, False)
        set_conference_member(model_id, False)

        if not remove_custom_model(model_id):
            return

        self.state.reload_models()
        self.state.reload_lists()

        if self.state.current == model_id:
            self._fallback_to_core()

        self._refresh_list()

    def _fallback_to_core(self) -> None:
        """Возвращает Гипериона, если активная модель больше не работает."""

        set_current_model_id(DEFAULT_MODEL_ID)
        self.state.current = DEFAULT_MODEL_ID

        if self.on_activate is not None:
            fallback = get_model(DEFAULT_MODEL_ID)

            if fallback is not None:
                self.on_activate(fallback)

    def _toggle_companion(self, checked: bool) -> None:
        """Включает или выключает модель в списке компаньонов."""

        model = self._selected_model()

        if model is None:
            return

        if not set_companion(model["id"], checked):
            return

        self.state.reload_lists()
        self._refresh_list(model["id"])

    def _toggle_conference(self, checked: bool) -> None:
        """Включает или выключает модель в сенате."""

        model = self._selected_model()

        if model is None:
            return

        if not set_conference_member(model["id"], checked):
            return

        self.state.reload_lists()
        self._refresh_list(model["id"])

    def _toggle_group(self, group: str, enabled: bool) -> None:
        """Включает или выключает группу моделей целиком."""

        if not set_model_group_enabled(group, enabled):
            return

        self.state.reload_groups()

        active = self.state.find(self.state.current)

        # Активная модель выключенной группы больше не работает.
        if active is not None and not self.state.model_usable(active):
            self._fallback_to_core()

        current = self._selected_model()
        keep_id = (
            current["id"]
            if current is not None and self.state.model_usable(current)
            else None
        )

        self._refresh_list(keep_id)

    def _open_params(self) -> None:
        """Открывает паспорт выбранной модели."""

        model = self._selected_model()

        if model is not None:
            show_model_params_dialog(self, model)

    def _open_site(self) -> None:
        """Открывает сайт модели в браузере."""

        model = self._selected_model()

        if model is None or not model["url"]:
            return

        QDesktopServices.openUrl(QUrl(model["url"]))

    def _connect_api(self) -> None:
        """Показывает состояние подключения API."""

        model = self._selected_model()

        if model is None:
            return

        QMessageBox.information(
            self,
            "Подключение API",
            f"Канал для модели «{model['name']}» ещё не настроен.\n"
            "Когда появится ключ доступа, подключение появится здесь."
            + (
                f"\nДоступ: {model['price']}."
                if model["price"]
                else ""
            ),
        )


def show_models_dialog(parent, on_activate=None) -> None:
    """Открывает окно «Модель»: закладки, карточка, репутация, активация."""

    state = ModelsState.load()

    if not state.models:
        QMessageBox.warning(
            parent,
            "Модель",
            "Каталог моделей не найден: data/models.json.",
        )

        return

    dialog = ModelsDialog(parent, state, on_activate)

    show_tool_window(parent, dialog, "models")
