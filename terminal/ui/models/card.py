# Giperion/terminal/ui/models/card.py                                  v001
# Карточка модели: портрет, шкалы, функции, лимиты и репутация.
# Последнее изменение: вынесено из show_models_dialog.

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import BASE_DIR
from terminal.core.model_registry import (
    build_stars,
    get_reputation,
    get_usage,
)
from terminal.core.model_settings import GROUP_LABELS, model_group_key
from terminal.ui.value_text import (
    CAPABILITY_FEATURES,
    capability_score,
    capability_value_text,
    format_percent,
    format_tokens,
    model_capabilities,
    model_modalities_text,
    tokens_word,
)


class ModelCard(QWidget):
    """Правая колонка окна «Модель»: карточка выбранной модели."""

    params_requested = Signal()
    companion_toggled = Signal(bool)
    conference_toggled = Signal(bool)
    site_requested = Signal()
    api_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("modelCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.name_label = QLabel(self)
        self.name_label.setObjectName("modelName")
        self.name_label.setWordWrap(True)

        self.nick_label = QLabel(self)
        self.nick_label.setObjectName("modelNickname")
        self.nick_label.setWordWrap(True)

        self.params_button = QPushButton("Параметры ИИ", self)
        self.params_button.setObjectName("aiParamsButton")
        self.params_button.setCursor(Qt.ArrowCursor)
        self.params_button.setFocusPolicy(Qt.NoFocus)
        self.params_button.setToolTip(
            "Паспорт модели: архитектура, качество, скорость и динамика."
        )
        self.params_button.clicked.connect(self.params_requested.emit)

        nick_row = QHBoxLayout()
        nick_row.setContentsMargins(0, 0, 0, 0)
        nick_row.setSpacing(8)
        nick_row.addWidget(self.nick_label, 1)
        nick_row.addWidget(self.params_button, 0, Qt.AlignRight)

        self.provider_label = QLabel(self)
        self.provider_label.setObjectName("modelProvider")

        identity = QHBoxLayout()
        identity.setSpacing(12)

        self.avatar_label = QLabel(self)
        self.avatar_label.setObjectName("modelAvatar")
        self.avatar_label.setFixedSize(96, 96)
        self.avatar_label.setAlignment(Qt.AlignCenter)

        self.strengths_widget = QWidget(self)
        self.strengths_layout = QVBoxLayout(self.strengths_widget)
        self.strengths_layout.setContentsMargins(0, 0, 0, 0)
        self.strengths_layout.setSpacing(3)

        identity.addWidget(self.avatar_label)
        identity.addWidget(self.strengths_widget, 1)

        self.strengths_caption = QLabel("ЧТО УМЕЕТ · ОЦЕНКА 0–5", self)
        self.strengths_caption.setObjectName("infoCaption")

        self.description_label = QLabel(self)
        self.description_label.setObjectName("modelDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.capabilities_caption = QLabel("ФУНКЦИИ МОДЕЛИ", self)
        self.capabilities_caption.setObjectName("infoCaption")

        self.capabilities_widget = QWidget(self)
        self.capabilities_layout = QVBoxLayout(self.capabilities_widget)
        self.capabilities_layout.setContentsMargins(0, 0, 0, 0)
        self.capabilities_layout.setSpacing(4)

        self.modalities_label = QLabel(self)
        self.modalities_label.setObjectName("dialogHint")
        self.modalities_label.setWordWrap(True)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("modelStatus")
        self.status_label.setWordWrap(True)

        self.companion_checkbox = QCheckBox("Компаньон", self)
        self.companion_checkbox.setObjectName("companionCheck")
        self.companion_checkbox.setToolTip(
            "Отмечает модель в закладке «Компаньоны». "
            "Отмеченные модели доступны как помощники."
        )
        self.companion_checkbox.setVisible(False)
        self.companion_checkbox.toggled.connect(
            self.companion_toggled.emit
        )

        self.conference_checkbox = QCheckBox("Участник сената", self)
        self.conference_checkbox.setObjectName("conferenceCheck")
        self.conference_checkbox.setVisible(False)
        self.conference_checkbox.toggled.connect(
            self.conference_toggled.emit
        )

        layout.addWidget(self.name_label)
        layout.addLayout(nick_row)
        layout.addWidget(self.provider_label)
        layout.addWidget(self.strengths_caption)
        layout.addLayout(identity)
        layout.addWidget(self.description_label)
        layout.addWidget(self.capabilities_caption)
        layout.addWidget(self.capabilities_widget)
        layout.addWidget(self.modalities_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.companion_checkbox)
        layout.addWidget(self.conference_checkbox)

        self._build_limits(layout)
        self._build_footer(layout)

        self._model_widgets = (
            self.avatar_label,
            self.nick_label,
            self.strengths_caption,
            self.strengths_widget,
            self.description_label,
            self.capabilities_caption,
            self.capabilities_widget,
            self.modalities_label,
            self.status_label,
            self.companion_checkbox,
            self.conference_checkbox,
            self.tokens_caption,
            self.context_caption,
            self.context_value,
            self.available_caption,
            self.available_value,
            self.used_caption,
            self.used_value,
            self.price_caption,
            self.price_value,
            self.site_button,
            self.api_button,
            self.reputation_caption,
            self.reputation_bar,
            self.reputation_label,
        )

    def _info_caption(self, text: str) -> QLabel:
        """Подпись строки в блоке лимитов."""

        label = QLabel(text, self)
        label.setObjectName("infoCaption")

        return label

    def _build_limits(self, layout: QVBoxLayout) -> None:
        """Блок лимитов, токенов и доступа."""

        self.tokens_caption = QLabel("ЛИМИТЫ, ТОКЕНЫ, ДОСТУП", self)
        self.tokens_caption.setObjectName("infoCaption")

        tokens_grid = QGridLayout()
        tokens_grid.setHorizontalSpacing(12)
        tokens_grid.setVerticalSpacing(4)

        self.context_value = QLabel(self)
        self.context_value.setObjectName("infoValue")

        self.available_value = QLabel(self)
        self.available_value.setObjectName("infoValue")

        self.used_value = QLabel(self)
        self.used_value.setObjectName("infoValue")

        self.price_value = QLabel(self)
        self.price_value.setObjectName("infoValue")

        self.context_caption = self._info_caption("Лимит контекста")
        self.available_caption = self._info_caption("Доступно токенов")
        self.used_caption = self._info_caption("Использовано токенов")
        self.price_caption = self._info_caption("Доступ")

        tokens_grid.addWidget(self.context_caption, 0, 0)
        tokens_grid.addWidget(self.context_value, 0, 1)
        tokens_grid.addWidget(self.available_caption, 1, 0)
        tokens_grid.addWidget(self.available_value, 1, 1)
        tokens_grid.addWidget(self.used_caption, 2, 0)
        tokens_grid.addWidget(self.used_value, 2, 1)
        tokens_grid.addWidget(self.price_caption, 3, 0)
        tokens_grid.addWidget(self.price_value, 3, 1)

        layout.addWidget(self.tokens_caption)
        layout.addLayout(tokens_grid)

    def _build_footer(self, layout: QVBoxLayout) -> None:
        """Ссылки на сайт, API и репутация модели."""

        links_row = QHBoxLayout()
        links_row.setSpacing(8)

        self.site_button = QPushButton("Сайт модели", self)
        self.site_button.setObjectName("siteButton")
        self.site_button.setCursor(Qt.ArrowCursor)
        self.site_button.setMinimumHeight(36)
        self.site_button.setMinimumWidth(186)
        self.site_button.clicked.connect(self.site_requested.emit)

        self.api_button = QPushButton("Подключить API", self)
        self.api_button.setObjectName("apiButton")
        self.api_button.setCursor(Qt.ArrowCursor)
        self.api_button.setMinimumHeight(36)
        self.api_button.clicked.connect(self.api_requested.emit)

        links_row.addWidget(self.site_button)
        links_row.addWidget(self.api_button)
        links_row.addStretch(1)

        self.reputation_caption = QLabel("РЕПУТАЦИЯ", self)
        self.reputation_caption.setObjectName("reputationCaption")

        self.reputation_bar = QProgressBar(self)
        self.reputation_bar.setObjectName("reputationBar")
        self.reputation_bar.setRange(0, 100)
        self.reputation_bar.setTextVisible(False)
        self.reputation_bar.setFixedHeight(14)

        self.reputation_label = QLabel(self)
        self.reputation_label.setObjectName("reputationLabel")
        self.reputation_label.setWordWrap(True)

        layout.addLayout(links_row)
        layout.addStretch(1)
        layout.addWidget(self.reputation_caption)
        layout.addWidget(self.reputation_bar)
        layout.addWidget(self.reputation_label)

    def show_model(
        self,
        model: dict | None,
        *,
        current: str,
        companions: set[str],
        conference: set[str],
        enabled: bool,
        usable: bool,
    ) -> None:
        """Заполняет карточку выбранной моделью или пустым состоянием."""

        for widget in self._model_widgets:
            widget.setVisible(model is not None)

        self.params_button.setEnabled(model is not None)

        if model is None:
            self.name_label.setText("Выбери модель")
            self.nick_label.setText("")
            self.provider_label.setText("")
            self._fill_avatar(None)
            self._fill_strengths(None)
            self._fill_capabilities(None)

            return

        active = model["id"] == current

        self.name_label.setText(model["name"])
        self.nick_label.setText(f"НИК: {model['nickname']}")
        self.provider_label.setText(model["provider"])
        self.description_label.setText(
            model["description"] or "Описание пока не заполнено."
        )

        self._fill_avatar(model)
        self._fill_strengths(model)
        self._fill_capabilities(model)

        self.status_label.setText(
            self._status_text(
                model,
                active=active,
                enabled=enabled,
                companions=companions,
                conference=conference,
            )
        )
        self.status_label.setStyleSheet(
            "" if enabled else "color: #ff9a6a;"
        )

        self.companion_checkbox.blockSignals(True)
        self.companion_checkbox.setChecked(model["id"] in companions)
        self.companion_checkbox.blockSignals(False)
        self.companion_checkbox.setVisible(True)
        self.companion_checkbox.setEnabled(usable)

        self.conference_checkbox.blockSignals(True)
        self.conference_checkbox.setChecked(model["id"] in conference)
        self.conference_checkbox.blockSignals(False)
        self.conference_checkbox.setVisible(True)
        self.conference_checkbox.setEnabled(usable)

        usage = get_usage(model["id"])

        self.context_value.setText(
            f"{format_tokens(usage['context_limit'])} "
            f"{tokens_word(usage['context_limit'])}"
            if usage["context_limit"]
            else "—"
        )
        self.available_value.setText(
            f"{format_tokens(usage['tokens_available'])} из "
            f"{format_tokens(usage['token_budget'])}"
            if usage["token_budget"]
            else "—"
        )
        self.used_value.setText(
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
        self.price_value.setText(
            price_labels.get(model["price"], model["price"] or "—")
        )

        self.site_button.setText("Сайт модели")
        self.site_button.setEnabled(bool(model["url"]))

        if model["api"] == "local":
            self.api_button.setText("Локальное ядро")
            self.api_button.setEnabled(False)
        elif model["available"]:
            self.api_button.setText("API подключено")
            self.api_button.setEnabled(False)
        else:
            self.api_button.setText("Подключить API")
            self.api_button.setEnabled(True)

        reputation = get_reputation(model["id"])

        self.reputation_bar.setValue(reputation["percent"])
        self.reputation_label.setText(
            f"{build_stars(reputation['stars'])}    "
            f"{reputation['requests']} обращений · "
            f"{reputation['percent']} % от самой частой модели"
        )

    def _status_text(
        self,
        model: dict,
        *,
        active: bool,
        enabled: bool,
        companions: set[str],
        conference: set[str],
    ) -> str:
        """Собирает строку статуса с пометками списков."""

        if active:
            status = "Статус: активна — отвечает в чате."
        elif not enabled:
            group_label = GROUP_LABELS.get(
                model_group_key(model),
                "группа моделей",
            )
            status = (
                "Статус: недоступна — группа "
                f"«{group_label}» выключена."
            )
        elif not model["available"] and model["group"] == "own":
            status = "Статус: недоступна — канал не настроен."
        elif model["available"]:
            status = "Статус: подключена — можно активировать."
        else:
            status = (
                "Статус: не подключена — вместо неё ответит заглушка."
            )

        if model["id"] in companions:
            status += " · компаньон."

        if model["id"] in conference:
            status += " · участник сената."

        return status

    def _clear_layout(self, layout) -> None:
        """Убирает старые строки до следующей отрисовки карточки."""

        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _fill_strengths(self, model: dict | None) -> None:
        """Перерисовывает шкалы сильных сторон модели."""

        self._clear_layout(self.strengths_layout)

        if model is None:
            return

        strengths = model.get("strengths") or {}

        if not strengths:
            empty = QLabel(
                "Сильные стороны не указаны",
                self.strengths_widget,
            )
            empty.setObjectName("strengthName")
            self.strengths_layout.addWidget(empty)

            return

        for strength_name, value in strengths.items():
            row = QWidget(self.strengths_widget)

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

            self.strengths_layout.addWidget(row)

    def _fill_capabilities(self, model: dict | None) -> None:
        """Перерисовывает таблицу функций и сравнение с другими моделями."""

        self._clear_layout(self.capabilities_layout)

        if model is None:
            return

        capabilities = model_capabilities(model)

        if not capabilities:
            empty = QLabel(
                "Для этой модели функции ещё не указаны.",
                self.capabilities_widget,
            )
            empty.setObjectName("strengthName")
            self.capabilities_layout.addWidget(empty)
            self.capabilities_widget.setFixedHeight(24)
            self.modalities_label.setText(
                "Добавь описание функций в data/models.json."
            )

            return

        for key, title in CAPABILITY_FEATURES:
            row = QWidget(self.capabilities_widget)
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
            self.capabilities_layout.addWidget(row)

        self.capabilities_widget.setFixedHeight(
            len(CAPABILITY_FEATURES) * 18
            + (len(CAPABILITY_FEATURES) - 1)
            * self.capabilities_layout.spacing()
        )
        self.modalities_label.setText(model_modalities_text(model))

    def _fill_avatar(self, model: dict | None) -> None:
        """Ставит портрет модели или знак ядра."""

        self.avatar_label.setPixmap(QPixmap())
        self.avatar_label.setText("")

        if model is None:
            return

        avatar_path = model.get("avatar", "")

        if avatar_path:
            path = BASE_DIR / avatar_path

            if path.exists():
                pixmap = QPixmap(str(path))

                if not pixmap.isNull():
                    self.avatar_label.setPixmap(
                        pixmap.scaled(
                            96,
                            96,
                            Qt.KeepAspectRatio,
                            Qt.SmoothTransformation,
                        )
                    )

                    return

        self.avatar_label.setText("◈")
