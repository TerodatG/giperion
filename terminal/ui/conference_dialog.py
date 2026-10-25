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
from terminal.ui.dialogs_base import SkinDialog


def show_conference_dialog(parent) -> None:
    """Открывает настройки режимов сената."""

    members = order_models_by_reputation(
        get_conference_members()
    )

    if members:
        lines = []

        for index, model in enumerate(members):
            nickname = model.get("nickname") or model["name"]
            lines.append(
                f"{senator_title(index + 1)} — {nickname}"
            )

        members_text = "\n".join(lines)

        if len(members) > MAX_CONFERENCE_MODELS:
            members_text += (
                "\n\nВ совет входят первые три по репутации, "
                "остальные остаются в резерве."
            )
    else:
        members_text = (
            "Пока никто не отмечен. Поставь галочку «Участник "
            "сената» в карточке модели."
        )

    dialog = SkinDialog(
        parent,
        "Вид сената",
        min_width=920,
        min_height=700,
    )

    layout = dialog.body_layout

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

    body = QHBoxLayout()
    body.setSpacing(12)

    # --- Слева: вертикальный каталог режимов ---
    left = QVBoxLayout()
    left.setSpacing(6)

    left_caption = QLabel("РЕЖИМЫ", dialog)
    left_caption.setObjectName("infoCaption")

    left_frame = QWidget(dialog)
    left_frame.setObjectName("conferenceScreenFrame")

    left_frame_layout = QVBoxLayout(left_frame)
    left_frame_layout.setContentsMargins(6, 6, 6, 6)
    left_frame_layout.setSpacing(0)

    view = QListWidget(dialog)
    view.setObjectName("conferenceModesView")
    view.setSelectionMode(QListWidget.SingleSelection)
    view.setMinimumWidth(250)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    left_frame_layout.addWidget(view)
    left.addWidget(left_caption)
    left.addWidget(left_frame, 1)

    # --- Справа: карточка выбранного режима ---
    right = QVBoxLayout()
    right.setSpacing(6)

    right_caption = QLabel("КАРТОЧКА РЕЖИМА", dialog)
    right_caption.setObjectName("infoCaption")

    right_frame = QWidget(dialog)
    right_frame.setObjectName("conferenceScreenFrame")

    right_frame_layout = QVBoxLayout(right_frame)
    right_frame_layout.setContentsMargins(6, 6, 6, 6)
    right_frame_layout.setSpacing(0)

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

    image = QLabel(card)
    image.setObjectName("conferenceImage")
    image.setFixedHeight(150)
    image.setAlignment(Qt.AlignCenter)

    name_label = QLabel(card)
    name_label.setObjectName("conferenceModeName")
    name_label.setWordWrap(True)

    summary_label = QLabel(card)
    summary_label.setObjectName("modelDescription")
    summary_label.setWordWrap(True)

    details_caption = QLabel("КАК РАБОТАЕТ", card)
    details_caption.setObjectName("infoCaption")

    details_label = QLabel(card)
    details_label.setObjectName("modelDescription")
    details_label.setWordWrap(True)

    members_caption = QLabel("УЧАСТНИКИ", card)
    members_caption.setObjectName("infoCaption")

    members_label = QLabel(card)
    members_label.setObjectName("modelDescription")
    members_label.setWordWrap(True)
    members_label.setText(members_text)

    card_layout.addWidget(image)
    card_layout.addWidget(name_label)
    card_layout.addWidget(summary_label)
    card_layout.addWidget(details_caption)
    card_layout.addWidget(details_label)
    card_layout.addWidget(members_caption)
    card_layout.addWidget(members_label)
    card_layout.addStretch(1)

    scroll.setWidget(card)
    right_frame_layout.addWidget(scroll)
    right.addWidget(right_caption)
    right.addWidget(right_frame, 1)

    body.addLayout(left, 1)
    body.addLayout(right, 2)

    # --- Нижняя строка ---
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

    def selected_mode() -> dict | None:
        """Режим, выбранный в левом списке."""

        item = view.currentItem()

        if item is None:
            return None

        mode_id = item.data(Qt.UserRole)

        return next(
            (
                mode
                for mode in CONFERENCE_MODES
                if mode["id"] == mode_id
            ),
            None,
        )

    def show_card() -> None:
        """Заполняет карточку выбранного режима."""

        mode = selected_mode()

        if mode is None:
            return

        name_label.setText(mode["name"])
        summary_label.setText(mode["summary"])
        details_label.setText(mode["details"])
        members_label.setText(members_text)

    def remember() -> None:
        """Сохраняет выбранный режим сената."""

        mode = selected_mode()

        if mode is None:
            return

        if not set_selected_mode_id(mode["id"]):
            status_label.setText("Не удалось сохранить режим.")
            return

        status_label.setText(f"Текущий режим: {mode['name']}.")

    selected_id = get_selected_mode_id()
    selected_row = 0

    for index, mode in enumerate(CONFERENCE_MODES):
        item = QListWidgetItem(mode["name"], view)
        item.setData(Qt.UserRole, mode["id"])
        item.setSizeHint(QSize(0, 38))
        item.setToolTip(mode["summary"])

        if mode["id"] == selected_id:
            selected_row = index

    view.currentItemChanged.connect(
        lambda current, previous: show_card()
    )
    remember_button.clicked.connect(remember)

    view.setCurrentRow(selected_row)
    show_card()

    current_mode = selected_mode()

    if current_mode is not None:
        status_label.setText(
            f"Текущий режим: {current_mode['name']}."
        )

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addLayout(body, 1)
    layout.addLayout(buttons_row)

    dialog.exec()
