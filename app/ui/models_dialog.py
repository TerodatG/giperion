# Giperion/app/ui/models_dialog.py                                  v007
# Окно «Модель»: каталог, карточка, свои модели и компаньоны.
# Последнее изменение: сенаторы, значки и сортировка конференции.

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from app.core.model_registry import (
    COMPANION_GROUP,
    CONFERENCE_GROUP,
    DEFAULT_MODEL_ID,
    MODEL_GROUPS,
    build_stars,
    get_current_model_id,
    get_reputation,
    get_usage,
    load_companion_ids,
    load_conference_ids,
    load_models,
    set_companion,
    set_conference_member,
    set_current_model_id,
)
from app.core.conference_roster import (
    MAX_CONFERENCE_MODELS,
    order_models_by_reputation,
    senator_title,
)
from app.ui.add_model_dialog import show_add_model_dialog
from app.ui.dialogs_base import SkinDialog
from app.ui.model_list_widgets import (
    SENATOR_ICON_ROLE,
    ModelListDelegate,
)
from app.ui.value_text import (
    CAPABILITY_FEATURES,
    build_model_item_text,
    capability_score,
    capability_value_text,
    format_percent,
    format_tokens,
    model_capabilities,
    model_modalities_text,
    tokens_word,
)
from config import BASE_DIR


def show_models_dialog(parent, on_activate=None) -> None:
    """Открывает окно «Модель»: закладки, карточка, репутация, активация.

    Первым в списке всегда идёт Гиперион — собственное ядро проекта.
    Карточка показывает сильные стороны, лимиты токенов и репутацию.
    """

    state = {
        "current": get_current_model_id(),
        "models": load_models(),
        "companions": set(load_companion_ids()),
        "conference": set(load_conference_ids()),
    }

    if not state["models"]:
        QMessageBox.warning(
            parent,
            "Модель",
            "Каталог моделей не найден: data/models.json.",
        )

        return

    dialog = SkinDialog(
        parent,
        "Модель",
        min_width=1000,
        min_height=720,
    )

    layout = dialog.body_layout

    title = QLabel("МОДЕЛИ", dialog)
    title.setObjectName("dialogTitle")

    subtitle = QLabel(
        "Выбери модель и нажми «Активировать». Карточка показывает "
        "сильные стороны, функции, лимиты токенов и репутацию. Галочка "
        "«Компаньон Гипериона» разрешает помощь моделей, а закладка "
        "«Компаньоны» собирает отмеченные модели.",
        dialog,
    )
    subtitle.setObjectName("dialogHint")
    subtitle.setWordWrap(True)

    body = QHBoxLayout()
    body.setSpacing(12)

    # --- Левая колонка: закладки и список моделей ---

    left = QVBoxLayout()
    left.setSpacing(6)

    tabs = QTabBar(dialog)
    tabs.setObjectName("modelsTabs")
    tabs.setExpanding(False)
    tabs.setDrawBase(False)

    for group_key, group_label in MODEL_GROUPS:
        index = tabs.addTab(group_label)
        tabs.setTabData(index, group_key)

    view = QListWidget(dialog)
    view.setObjectName("modelsView")
    view.setSelectionMode(QListWidget.SingleSelection)
    view.setItemDelegate(ModelListDelegate(view))
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    view.setTextElideMode(Qt.ElideRight)

    list_frame = QWidget(dialog)
    list_frame.setObjectName("modelScreenFrame")

    list_frame_layout = QVBoxLayout(list_frame)
    list_frame_layout.setContentsMargins(6, 6, 6, 6)
    list_frame_layout.setSpacing(0)
    list_frame_layout.addWidget(view)

    add_button = QPushButton("+ Своя модель", dialog)
    add_button.setObjectName("addModelButton")
    add_button.setCursor(Qt.ArrowCursor)
    add_button.setVisible(False)

    empty_hint = QLabel("Своих моделей пока нет", dialog)
    empty_hint.setObjectName("dialogHint")
    empty_hint.setAlignment(Qt.AlignCenter)
    empty_hint.setVisible(False)

    left.addWidget(tabs)
    left.addWidget(list_frame, 1)
    left.addWidget(empty_hint)
    left.addWidget(add_button)

    # --- Правая колонка: карточка модели в прокрутке ---

    scroll = QScrollArea(dialog)
    scroll.setObjectName("cardScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    card = QWidget()
    card.setObjectName("modelCard")

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(16, 14, 16, 14)
    card_layout.setSpacing(10)

    name_label = QLabel(card)
    name_label.setObjectName("modelName")
    name_label.setWordWrap(True)

    nick_label = QLabel(card)
    nick_label.setObjectName("modelNickname")
    nick_label.setWordWrap(True)

    provider_label = QLabel(card)
    provider_label.setObjectName("modelProvider")

    identity = QHBoxLayout()
    identity.setSpacing(12)

    avatar_label = QLabel(card)
    avatar_label.setObjectName("modelAvatar")
    avatar_label.setFixedSize(96, 96)
    avatar_label.setAlignment(Qt.AlignCenter)

    strengths_widget = QWidget(card)
    strengths_layout = QVBoxLayout(strengths_widget)
    strengths_layout.setContentsMargins(0, 0, 0, 0)
    strengths_layout.setSpacing(3)

    identity.addWidget(avatar_label)
    identity.addWidget(strengths_widget, 1)

    strengths_caption = QLabel("ЧТО УМЕЕТ · ОЦЕНКА 0–5", card)
    strengths_caption.setObjectName("infoCaption")

    description_label = QLabel(card)
    description_label.setObjectName("modelDescription")
    description_label.setWordWrap(True)
    description_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

    capabilities_caption = QLabel(
        "ФУНКЦИИ МОДЕЛИ",
        card,
    )
    capabilities_caption.setObjectName("infoCaption")

    capabilities_widget = QWidget(card)
    capabilities_layout = QVBoxLayout(capabilities_widget)
    capabilities_layout.setContentsMargins(0, 0, 0, 0)
    capabilities_layout.setSpacing(4)

    modalities_label = QLabel(card)
    modalities_label.setObjectName("dialogHint")
    modalities_label.setWordWrap(True)

    status_label = QLabel(card)
    status_label.setObjectName("modelStatus")
    status_label.setWordWrap(True)

    companion_checkbox = QCheckBox(
        "Компаньон Гипериона",
        card,
    )
    companion_checkbox.setObjectName("companionCheck")
    companion_checkbox.setToolTip(
        "Гиперион сможет обращаться к этой модели за помощью. "
        "Можно отметить несколько моделей: для ответа выберется "
        "лучшая по репутации и навыкам."
    )
    companion_checkbox.setVisible(False)

    conference_checkbox = QCheckBox(
        "Участник конференции",
        card,
    )
    conference_checkbox.setObjectName("conferenceCheck")
    conference_checkbox.setVisible(False)

    tokens_caption = QLabel("ЛИМИТЫ, ТОКЕНЫ, ДОСТУП", card)
    tokens_caption.setObjectName("infoCaption")

    tokens_grid = QGridLayout()
    tokens_grid.setHorizontalSpacing(12)
    tokens_grid.setVerticalSpacing(4)

    context_value = QLabel(card)
    context_value.setObjectName("infoValue")

    available_value = QLabel(card)
    available_value.setObjectName("infoValue")

    used_value = QLabel(card)
    used_value.setObjectName("infoValue")

    price_value = QLabel(card)
    price_value.setObjectName("infoValue")

    def info_caption(text: str) -> QLabel:
        """Подпись строки в блоке лимитов."""

        label = QLabel(text, card)
        label.setObjectName("infoCaption")

        return label

    context_caption = info_caption("Лимит контекста")
    available_caption = info_caption("Доступно токенов")
    used_caption = info_caption("Использовано токенов")
    price_caption = info_caption("Доступ")

    tokens_grid.addWidget(context_caption, 0, 0)
    tokens_grid.addWidget(context_value, 0, 1)
    tokens_grid.addWidget(available_caption, 1, 0)
    tokens_grid.addWidget(available_value, 1, 1)
    tokens_grid.addWidget(used_caption, 2, 0)
    tokens_grid.addWidget(used_value, 2, 1)
    tokens_grid.addWidget(price_caption, 3, 0)
    tokens_grid.addWidget(price_value, 3, 1)

    links_row = QHBoxLayout()
    links_row.setSpacing(8)

    site_button = QPushButton("Сайт модели", card)
    site_button.setObjectName("siteButton")
    site_button.setCursor(Qt.ArrowCursor)
    site_button.setMinimumHeight(36)
    site_button.setMinimumWidth(186)

    api_button = QPushButton("Подключить API", card)
    api_button.setObjectName("apiButton")
    api_button.setCursor(Qt.ArrowCursor)
    api_button.setMinimumHeight(36)

    links_row.addWidget(site_button)
    links_row.addWidget(api_button)
    links_row.addStretch(1)

    reputation_caption = QLabel("РЕПУТАЦИЯ", card)
    reputation_caption.setObjectName("reputationCaption")

    reputation_bar = QProgressBar(card)
    reputation_bar.setObjectName("reputationBar")
    reputation_bar.setRange(0, 100)
    reputation_bar.setTextVisible(False)
    reputation_bar.setFixedHeight(14)

    reputation_label = QLabel(card)
    reputation_label.setObjectName("reputationLabel")
    reputation_label.setWordWrap(True)

    card_layout.addWidget(name_label)
    card_layout.addWidget(nick_label)
    card_layout.addWidget(provider_label)
    card_layout.addWidget(strengths_caption)
    card_layout.addLayout(identity)
    card_layout.addWidget(description_label)
    card_layout.addWidget(capabilities_caption)
    card_layout.addWidget(capabilities_widget)
    card_layout.addWidget(modalities_label)
    card_layout.addWidget(status_label)
    card_layout.addWidget(companion_checkbox)
    card_layout.addWidget(conference_checkbox)
    card_layout.addWidget(tokens_caption)
    card_layout.addLayout(tokens_grid)
    card_layout.addLayout(links_row)
    card_layout.addStretch(1)
    card_layout.addWidget(reputation_caption)
    card_layout.addWidget(reputation_bar)
    card_layout.addWidget(reputation_label)

    scroll.setWidget(card)

    card_frame = QWidget(dialog)
    card_frame.setObjectName("modelScreenFrame")

    card_frame_layout = QVBoxLayout(card_frame)
    card_frame_layout.setContentsMargins(6, 6, 6, 6)
    card_frame_layout.setSpacing(0)
    card_frame_layout.addWidget(scroll)

    body.addLayout(left, 1)
    body.addWidget(card_frame, 1)

    # --- Кнопки окна ---

    buttons_row = QHBoxLayout()
    buttons_row.setSpacing(8)

    activate_button = QPushButton("Активировать", dialog)
    activate_button.setObjectName("activateButton")
    activate_button.setCursor(Qt.ArrowCursor)
    activate_button.setMinimumHeight(38)
    activate_button.setMinimumWidth(170)

    close_box = QDialogButtonBox(QDialogButtonBox.Ok, dialog)
    close_box.button(QDialogButtonBox.Ok).setText("Закрыть")
    close_box.accepted.connect(dialog.accept)

    buttons_row.addWidget(activate_button)
    buttons_row.addStretch(1)
    buttons_row.addWidget(close_box)

    # --- Наполнение карточки ---

    def visible_models() -> list[dict]:
        """Модели текущей закладки."""

        group = tabs.tabData(tabs.currentIndex())

        if group == COMPANION_GROUP:
            return [
                model
                for model in state["models"]
                if model["id"] in state["companions"]
            ]

        if group == CONFERENCE_GROUP:
            return order_models_by_reputation(
                [
                    model
                    for model in state["models"]
                    if model["id"] in state["conference"]
                ]
            )

        return [
            model
            for model in state["models"]
            if model["group"] == group
        ]

    def selected_model() -> dict | None:
        """Модель, выбранная в списке."""

        item = view.currentItem()

        if item is None:
            return None

        return next(
            (
                model
                for model in state["models"]
                if model["id"] == item.data(Qt.UserRole)
            ),
            None,
        )

    def fill_strengths(model: dict | None) -> None:
        """Перерисовывает шкалы сильных сторон модели."""

        while strengths_layout.count():
            item = strengths_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                # Убираем сразу, иначе при повторной отрисовке карточки
                # старые строки на миг накладываются на новые.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        if model is None:
            return

        strengths = model.get("strengths") or {}

        if not strengths:
            empty = QLabel(
                "Сильные стороны не указаны",
                strengths_widget,
            )
            empty.setObjectName("strengthName")
            strengths_layout.addWidget(empty)

            return

        for strength_name, value in strengths.items():
            row = QWidget(strengths_widget)

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            name = QLabel(strength_name, row)
            name.setObjectName("strengthName")
            name.setFixedWidth(92)

            bar = QProgressBar(row)
            bar.setObjectName("strengthBar")
            bar.setRange(0, 5)
            bar.setValue(value)
            bar.setTextVisible(False)
            bar.setFixedHeight(10)

            score = QLabel(str(value), row)
            score.setObjectName("strengthValue")
            score.setFixedWidth(14)

            row_layout.addWidget(name)
            row_layout.addWidget(bar, 1)
            row_layout.addWidget(score)

            strengths_layout.addWidget(row)

    def fill_capabilities(model: dict | None) -> None:
        """Перерисовывает таблицу функций и сравнение с другими моделями."""

        while capabilities_layout.count():
            item = capabilities_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        if model is None:
            return

        capabilities = model_capabilities(model)

        if not capabilities:
            empty = QLabel(
                "Для этой модели функции ещё не указаны.",
                capabilities_widget,
            )
            empty.setObjectName("strengthName")
            capabilities_layout.addWidget(empty)
            capabilities_widget.setFixedHeight(24)
            modalities_label.setText(
                "Добавь описание функций в data/models.json."
            )

            return

        for key, title in CAPABILITY_FEATURES:
            row = QWidget(capabilities_widget)
            row.setFixedHeight(18)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(7)

            name = QLabel(title, row)
            name.setObjectName("capabilityName")
            name.setFixedWidth(154)

            bar = QProgressBar(row)
            bar.setObjectName("capabilityBar")
            bar.setRange(0, 5)
            bar.setValue(capability_score(model, key))
            bar.setTextVisible(False)
            bar.setFixedHeight(9)
            bar.setMinimumWidth(28)

            value = QLabel(
                capability_value_text(model, key),
                row,
            )
            value.setObjectName("capabilityValue")
            value.setFixedWidth(38)

            row_layout.addWidget(name)
            row_layout.addWidget(bar, 1)
            row_layout.addWidget(value)
            capabilities_layout.addWidget(row)

        capabilities_widget.setFixedHeight(
            len(CAPABILITY_FEATURES) * 18
            + (len(CAPABILITY_FEATURES) - 1)
            * capabilities_layout.spacing()
        )
        modalities_label.setText(model_modalities_text(model))

    def fill_avatar(model: dict | None) -> None:
        """Ставит портрет модели или знак ядра."""

        avatar_label.setPixmap(QPixmap())
        avatar_label.setText("")

        if model is None:
            return

        avatar_path = model.get("avatar", "")

        if avatar_path:
            path = BASE_DIR / avatar_path

            if path.exists():
                pixmap = QPixmap(str(path))

                if not pixmap.isNull():
                    avatar_label.setPixmap(
                        pixmap.scaled(
                            96,
                            96,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        )
                    )

                    return

        avatar_label.setText("◈")

    def show_card() -> None:
        """Заполняет карточку выбранной модели."""

        model = selected_model()

        declare_widgets = (
            avatar_label,
            nick_label,
            strengths_caption,
            strengths_widget,
            description_label,
            capabilities_caption,
            capabilities_widget,
            modalities_label,
            status_label,
            companion_checkbox,
            conference_checkbox,
            tokens_caption,
            context_caption,
            context_value,
            available_caption,
            available_value,
            used_caption,
            used_value,
            price_caption,
            price_value,
            site_button,
            api_button,
            reputation_caption,
            reputation_bar,
            reputation_label,
        )

        for widget in declare_widgets:
            widget.setVisible(model is not None)

        activate_button.setEnabled(False)

        if model is None:
            name_label.setText("Выбери модель")
            nick_label.setText("")
            provider_label.setText("")
            fill_avatar(None)
            fill_strengths(None)
            fill_capabilities(None)

            return

        active = model["id"] == state["current"]

        name_label.setText(model["name"])
        nick_label.setText(f"НИК: {model['nickname']}")
        provider_label.setText(model["provider"])
        description_label.setText(
            model["description"] or "Описание пока не заполнено."
        )

        fill_avatar(model)
        fill_strengths(model)
        fill_capabilities(model)

        if active:
            status = "Статус: активна — отвечает в чате."
        elif model["available"]:
            status = "Статус: подключена — можно активировать."
        elif model["group"] == "own":
            status = "Статус: своя модель — канал ещё не настроен."
        else:
            status = (
                "Статус: не подключена — вместо неё ответит заглушка."
            )

        is_helper = model["id"] in state["companions"]
        is_conference = model["id"] in state["conference"]

        if is_helper:
            status += " · компаньон Гипериона."

        if is_conference:
            status += " · участник конференции."

        status_label.setText(status)

        companion_checkbox.blockSignals(True)
        companion_checkbox.setChecked(is_helper)
        companion_checkbox.blockSignals(False)
        companion_checkbox.setVisible(
            model["id"] != DEFAULT_MODEL_ID
        )
        companion_checkbox.setEnabled(
            model["id"] != DEFAULT_MODEL_ID
        )

        conference_checkbox.blockSignals(True)
        conference_checkbox.setChecked(is_conference)
        conference_checkbox.blockSignals(False)
        conference_checkbox.setVisible(True)
        conference_checkbox.setEnabled(True)

        usage = get_usage(model["id"])

        context_value.setText(
            f"{format_tokens(usage['context_limit'])} "
            f"{tokens_word(usage['context_limit'])}"
            if usage["context_limit"]
            else "—"
        )
        available_value.setText(
            f"{format_tokens(usage['tokens_available'])} из "
            f"{format_tokens(usage['token_budget'])}"
            if usage["token_budget"]
            else "—"
        )
        used_value.setText(
            f"{format_tokens(usage['tokens_used'])} "
            f"({format_percent(usage['tokens_used'] * 100 / usage['token_budget'])}"
            f" % бюджета)"
            if usage["token_budget"]
            else "—"
        )

        price_labels = {
            "бесплатно": f"бесплатно ({model['provider']})",
            "локально": "локально, без интернета",
        }
        price_value.setText(
            price_labels.get(model["price"], model["price"] or "—")
        )

        site_button.setText("Сайт модели")
        site_button.setEnabled(bool(model["url"]))

        if model["api"] == "local":
            api_button.setText("Локальное ядро")
            api_button.setEnabled(False)
        elif model["available"]:
            api_button.setText("API подключено")
            api_button.setEnabled(False)
        else:
            api_button.setText("Подключить API")
            api_button.setEnabled(True)

        reputation = get_reputation(model["id"])

        reputation_bar.setValue(reputation["percent"])
        reputation_label.setText(
            f"{build_stars(reputation['stars'])}    "
            f"{reputation['requests']} обращений · "
            f"{reputation['percent']} % от самой частой модели"
        )

        activate_button.setEnabled(not active)

    def refresh_list(keep_id: str | None = None) -> None:
        """Перерисовывает список текущей закладки.

        keep_id позволяет сохранить выбор после переключения галочки
        компаньона, не возвращаясь к активной модели.
        """

        view.blockSignals(True)
        view.clear()

        group = tabs.tabData(tabs.currentIndex())
        is_conference = group == CONFERENCE_GROUP

        for index, model in enumerate(visible_models()):
            text = build_model_item_text(
                model,
                state["current"],
                state["companions"],
            )

            senator_slot = is_conference and (
                index < MAX_CONFERENCE_MODELS
            )

            if is_conference:
                text = f"{senator_title(index + 1)} · {text}"

            item = QListWidgetItem(text, view)
            item.setData(Qt.UserRole, model["id"])
            item.setData(SENATOR_ICON_ROLE, senator_slot)

            font = item.font()
            is_active = model["id"] == state["current"]
            font.setBold(is_active)
            item.setFont(font)

            if is_active:
                item.setForeground(QColor("#7cf58f"))
            elif model["available"]:
                item.setForeground(QColor("#cfe8d2"))
            else:
                item.setForeground(QColor("#94a497"))

        target_id = keep_id or state["current"]
        row = 0

        for index in range(view.count()):
            if view.item(index).data(Qt.UserRole) == target_id:
                row = index

                break

        if view.count():
            view.setCurrentRow(row)
            view.doItemsLayout()

        view.blockSignals(False)

        is_own = group == "own"
        is_companions = group == COMPANION_GROUP

        if is_companions:
            empty_hint.setText(
                "Компаньонов пока нет.\n"
                "Отметь модель галочкой в её карточке."
            )
        elif is_conference:
            empty_hint.setText(
                "Участников конференции пока нет.\n"
                "Отметь модель галочкой в её карточке."
            )
        else:
            empty_hint.setText("Своих моделей пока нет")

        empty_hint.setVisible(
            (is_own or is_companions or is_conference)
            and view.count() == 0
        )

        show_card()

    def group_changed(index: int) -> None:
        """Переключает закладку и показывает свои модели."""

        add_button.setVisible(tabs.tabData(index) == "own")
        refresh_list()

    def activate() -> None:
        """Активирует выбранную модель, не закрывая окно."""

        model = selected_model()

        if model is None or model["id"] == state["current"]:
            return

        if not set_current_model_id(model["id"]):
            return

        state["current"] = model["id"]

        refresh_list()

        if on_activate is not None:
            on_activate(model)

    def add_own_model() -> None:
        """Добавляет свою модель и показывает её в списке."""

        model = show_add_model_dialog(dialog)

        if model is None:
            return

        state["models"] = load_models()

        for index in range(tabs.count()):
            if tabs.tabData(index) == "own":
                tabs.setCurrentIndex(index)

                break

        refresh_list()

        for row in range(view.count()):
            if view.item(row).data(Qt.UserRole) == model["id"]:
                view.setCurrentRow(row)

                break

    def toggle_companion(checked: bool) -> None:
        """Включает или выключает модель в списке компаньонов."""

        model = selected_model()

        if model is None or model["id"] == DEFAULT_MODEL_ID:
            return

        if not set_companion(model["id"], checked):
            return

        state["companions"] = set(load_companion_ids())
        refresh_list(model["id"])

    def toggle_conference(checked: bool) -> None:
        """Включает или выключает модель в конференции."""

        model = selected_model()

        if model is None:
            return

        if not set_conference_member(model["id"], checked):
            return

        state["conference"] = set(load_conference_ids())
        refresh_list(model["id"])

    def open_site() -> None:
        """Открывает сайт модели в браузере."""

        model = selected_model()

        if model is None or not model["url"]:
            return

        QDesktopServices.openUrl(QUrl(model["url"]))

    def connect_api() -> None:
        """Показывает состояние подключения API."""

        model = selected_model()

        if model is None:
            return

        QMessageBox.information(
            dialog,
            "Подключение API",
            f"Канал для модели «{model['name']}» ещё не настроен.\n"
            "Когда появится ключ доступа, подключение появится здесь."
            + (
                f"\nДоступ: {model['price']}."
                if model["price"]
                else ""
            ),
        )

    tabs.currentChanged.connect(group_changed)
    view.currentItemChanged.connect(
        lambda current, previous: show_card()
    )
    activate_button.clicked.connect(activate)
    add_button.clicked.connect(add_own_model)
    companion_checkbox.toggled.connect(toggle_companion)
    conference_checkbox.toggled.connect(toggle_conference)
    site_button.clicked.connect(open_site)
    api_button.clicked.connect(connect_api)

    # Открываем ту закладку, где находится активная модель.
    current_model = next(
        (
            model
            for model in state["models"]
            if model["id"] == state["current"]
        ),
        None,
    )

    start_index = 0

    if current_model is not None:
        for index in range(tabs.count()):
            if tabs.tabData(index) == current_model["group"]:
                start_index = index

                break

    tabs.setCurrentIndex(start_index)
    refresh_list()

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addLayout(body, 1)
    layout.addLayout(buttons_row)

    def finish_initial_layout() -> None:
        """Пересчитывает строки после применения стилей окна."""

        view.doItemsLayout()
        view.viewport().update()

    # Первый расчёт до показа окна использует ещё не применённые метрики
    # QSS, из-за чего подсветка первой строки наезжает на соседнюю.
    QTimer.singleShot(0, finish_initial_layout)
    dialog.exec()
