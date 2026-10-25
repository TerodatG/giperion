# Giperion/app/ui/conference_dialog.py                              v003
# Окно «Вид сената»: список режимов слева и карточка справа.
# Последнее изменение: сенаторы и обычный шрифт названий режимов.

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from terminal.core.conference_catalog import (
    CONFERENCE_MODES,
    get_conference_members,
    get_selected_mode_id,
    set_selected_mode_id,
)
from terminal.core.conference_roster import (
    MAX_CONFERENCE_MODELS,
    order_models_by_reputation,
    senator_title,
)
from terminal.ui.dialogs_base import SkinDialog, show_tool_window


def _members_text(members: list[dict]) -> str:
    """Собирает подпись участников сената."""

    if not members:
        return (
            "Сейчас сенат не выбран. Отметь участников "
            "в каталоге моделей."
        )

    lines = []

    for index, model in enumerate(members):
        nickname = model.get("nickname") or model["name"]
        lines.append(f"{senator_title(index + 1)} — {nickname}")

    text = "\n".join(lines)

    if len(members) > MAX_CONFERENCE_MODELS:
        text += (
            "\n\nВ работу пойдут первые три по репутации, "
            "остальные остаются в запасе."
        )

    return text


def _build_modes(dialog) -> tuple[QVBoxLayout, QListWidget]:
    """Левая колонка: список режимов."""

    left = QVBoxLayout()
    left.setSpacing(6)

    caption = QLabel("РЕЖИМЫ", dialog)
    caption.setObjectName("infoCaption")

    frame = QWidget(dialog)
    frame.setObjectName("conferenceScreenFrame")

    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(6, 6, 6, 6)
    frame_layout.setSpacing(0)

    view = QListWidget(dialog)
    view.setObjectName("conferenceModesView")
    view.setSelectionMode(QListWidget.SingleSelection)
    view.setMinimumWidth(250)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    frame_layout.addWidget(view)
    left.addWidget(caption)
    left.addWidget(frame, 1)

    return left, view


def _build_card(dialog, members_text: str) -> tuple[QVBoxLayout, dict]:
    """Правая колонка: карточка режима."""

    right = QVBoxLayout()
    right.setSpacing(6)

    caption = QLabel("КАРТОЧКА РЕЖИМА", dialog)
    caption.setObjectName("infoCaption")

    frame = QWidget(dialog)
    frame.setObjectName("conferenceScreenFrame")

    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(6, 6, 6, 6)
    frame_layout.setSpacing(0)

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

    labels = {
        "image": QLabel(card),
        "name": QLabel(card),
        "summary": QLabel(card),
        "details": QLabel(card),
        "members": QLabel(card),
    }

    labels["image"].setObjectName("conferenceImage")
    labels["image"].setFixedHeight(150)
    labels["image"].setAlignment(Qt.AlignCenter)
    labels["name"].setObjectName("conferenceModeName")
    labels["name"].setWordWrap(True)
    labels["summary"].setObjectName("modelDescription")
    labels["summary"].setWordWrap(True)
    labels["details"].setObjectName("modelDescription")
    labels["details"].setWordWrap(True)
    labels["members"].setObjectName("modelDescription")
    labels["members"].setWordWrap(True)
    labels["members"].setText(members_text)

    details_caption = QLabel("КАК РАБОТАЕТ", card)
    details_caption.setObjectName("infoCaption")
    members_caption = QLabel("УЧАСТНИКИ", card)
    members_caption.setObjectName("infoCaption")

    card_layout.addWidget(labels["image"])
    card_layout.addWidget(labels["name"])
    card_layout.addWidget(labels["summary"])
    card_layout.addWidget(details_caption)
    card_layout.addWidget(labels["details"])
    card_layout.addWidget(members_caption)
    card_layout.addWidget(labels["members"])
    card_layout.addStretch(1)

    scroll.setWidget(card)
    frame_layout.addWidget(scroll)
    right.addWidget(caption)
    right.addWidget(frame, 1)

    return right, labels


def _fill_modes(view: QListWidget) -> None:
    """Заполняет список режимов и выбирает сохранённый."""

    selected_id = get_selected_mode_id()
    selected_row = 0

    for index, mode in enumerate(CONFERENCE_MODES):
        item = QListWidgetItem(mode["name"], view)
        item.setData(Qt.UserRole, mode["id"])
        item.setSizeHint(QSize(0, 38))
        item.setToolTip(mode["summary"])

        if mode["id"] == selected_id:
            selected_row = index

    view.setCurrentRow(selected_row)


def _selected_mode(view: QListWidget) -> dict | None:
    """Режим, выбранный в левом списке."""

    item = view.currentItem()

    if item is None:
        return None

    mode_id = item.data(Qt.UserRole)

    return next(
        (mode for mode in CONFERENCE_MODES if mode["id"] == mode_id),
        None,
    )


def _show_card(view: QListWidget, labels: dict, members_text: str) -> None:
    """Заполняет карточку выбранного режима."""

    mode = _selected_mode(view)

    if mode is None:
        return

    labels["name"].setText(mode["name"])
    labels["summary"].setText(mode["summary"])
    labels["details"].setText(mode["details"])
    labels["members"].setText(members_text)


def show_conference_dialog(parent) -> None:
    """Открывает каталог сценариев сената."""

    members = order_models_by_reputation(get_conference_members())
    members_text = _members_text(members)

    dialog = SkinDialog(
        parent,
        "Вид сената",
        min_width=920,
        min_height=700,
    )

    title = QLabel("СЕНАТ", dialog)
    title.setObjectName("dialogTitle")

    subtitle = QLabel(
        "Выбери сценарий. «Параллельный совет» запускается, когда "
        "включён модуль «Сенат» и отмечены участники. Дебаты "
        "и модератор пока подготовлены как задел.",
        dialog,
    )
    subtitle.setObjectName("dialogHint")
    subtitle.setWordWrap(True)

    left, view = _build_modes(dialog)
    right, labels = _build_card(dialog, members_text)

    body = QHBoxLayout()
    body.setSpacing(12)
    body.addLayout(left, 1)
    body.addLayout(right, 2)

    status_label = QLabel(dialog)
    status_label.setObjectName("dialogHint")

    remember_button = QPushButton("Запомнить режим", dialog)
    remember_button.setObjectName("activateButton")
    remember_button.setCursor(Qt.ArrowCursor)
    remember_button.setMinimumHeight(38)
    remember_button.setMinimumWidth(180)

    close_box = QDialogButtonBox(QDialogButtonBox.Ok, dialog)
    close_box.button(QDialogButtonBox.Ok).setText("Закрыть")
    close_box.accepted.connect(dialog.accept)

    buttons_row = QHBoxLayout()
    buttons_row.setSpacing(8)
    buttons_row.addWidget(status_label)
    buttons_row.addStretch(1)
    buttons_row.addWidget(remember_button)
    buttons_row.addWidget(close_box)

    def remember() -> None:
        """Сохраняет выбранный режим сената."""

        mode = _selected_mode(view)

        if mode is None:
            return

        if not set_selected_mode_id(mode["id"]):
            status_label.setText("Не удалось сохранить режим.")
            return

        status_label.setText(f"Текущий режим: {mode['name']}.")

    view.currentItemChanged.connect(
        lambda current, previous: _show_card(
            view,
            labels,
            members_text,
        )
    )
    remember_button.clicked.connect(remember)

    _fill_modes(view)
    _show_card(view, labels, members_text)

    current_mode = _selected_mode(view)

    if current_mode is not None:
        status_label.setText(
            f"Текущий режим: {current_mode['name']}."
        )

    dialog.body_layout.addWidget(title)
    dialog.body_layout.addWidget(subtitle)
    dialog.body_layout.addLayout(body, 1)
    dialog.body_layout.addLayout(buttons_row)

    show_tool_window(parent, dialog, "conference")
