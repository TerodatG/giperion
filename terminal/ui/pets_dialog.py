# Giperion/terminal/ui/pets_dialog.py                                v001
# Окно «Питомцы»: карточки маленьких моделей терминала.
# Последнее изменение: два базовых питомца, свои питомцы и закрепление.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from terminal.core.pets import (
    SPECIES_TITLES,
    add_custom_pet,
    get_active_pet_id,
    load_pets,
    set_active_pet_id,
)
from terminal.ui.dialogs_base import SkinDialog, show_tool_window


def _card_label(text: str, name: str, parent) -> QLabel:
    """Создаёт подпись карточки питомца."""

    label = QLabel(text, parent)
    label.setObjectName(name)
    label.setWordWrap(True)

    return label


def _build_pet_card(
    pet: dict,
    active: bool,
    refresh,
    on_change,
) -> QWidget:
    """Собирает карточку одного питомца."""

    card = QWidget()
    card.setObjectName("petCard")
    card.setAttribute(Qt.WA_StyledBackground, True)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(6)

    top = QHBoxLayout()
    top.setSpacing(10)

    avatar = QLabel(pet.get("symbol") or "🐾", card)
    avatar.setObjectName("petAvatar")
    avatar.setAlignment(Qt.AlignCenter)
    avatar.setFixedSize(56, 56)

    identity = QVBoxLayout()
    identity.setSpacing(2)

    name = _card_label(pet["name"], "petName", card)
    species = _card_label(
        pet.get("species_title") or SPECIES_TITLES["custom"],
        "petType",
        card,
    )

    identity.addWidget(name)
    identity.addWidget(species)

    top.addWidget(avatar)
    top.addLayout(identity, 1)

    description = _card_label(
        pet.get("description") or "Описание пока не заполнено.",
        "petDescription",
        card,
    )

    speech = _card_label(
        pet.get("speech") or "",
        "petHint",
        card,
    )

    status_text = (
        "Закреплён за терминалом"
        if active
        else "Свободен"
    )
    status = _card_label(status_text, "petStatus", card)
    status.setProperty("active", active)

    button = QPushButton(
        "Открепить" if active else "Закрепить",
        card,
    )
    button.setObjectName("petAttachButton")
    button.setCursor(Qt.ArrowCursor)
    button.setMinimumHeight(32)

    def toggle() -> None:
        """Закрепляет или освобождает питомца."""

        set_active_pet_id("" if active else pet["id"])

        if on_change is not None:
            on_change()

        refresh()

    button.clicked.connect(toggle)

    layout.addLayout(top)
    layout.addWidget(description)
    layout.addWidget(speech)
    layout.addStretch(1)
    layout.addWidget(status)
    layout.addWidget(button)

    return card


def _ask_new_pet(parent) -> dict | None:
    """Спрашивает имя и вид нового питомца."""

    dialog = SkinDialog(
        parent,
        "Новый питомец",
        min_width=540,
        min_height=360,
    )

    title = QLabel("НОВЫЙ ПИТОМЕЦ", dialog)
    title.setObjectName("dialogTitle")

    hint = QLabel(
        "Питомец копирует базовый шаблон личности Гипериона. "
        "Полноценная модель для него не нужна: общение идёт через "
        "локальное ядро терминала.",
        dialog,
    )
    hint.setObjectName("dialogHint")
    hint.setWordWrap(True)

    name_input = QLineEdit(dialog)
    name_input.setPlaceholderText("Имя питомца")
    name_input.setMaxLength(40)

    species_input = QComboBox(dialog)

    for key, value in SPECIES_TITLES.items():
        species_input.addItem(value, key)

    description_input = QPlainTextEdit(dialog)
    description_input.setPlaceholderText(
        "Короткое описание характера (необязательно)"
    )
    description_input.setMaximumHeight(90)

    form = QGridLayout()
    form.setSpacing(8)
    form.addWidget(QLabel("Имя:", dialog), 0, 0)
    form.addWidget(name_input, 0, 1)
    form.addWidget(QLabel("Вид:", dialog), 1, 0)
    form.addWidget(species_input, 1, 1)
    form.addWidget(QLabel("Описание:", dialog), 2, 0)
    form.addWidget(description_input, 2, 1)

    status = QLabel("", dialog)
    status.setObjectName("dialogHint")

    buttons = QDialogButtonBox(
        QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
        dialog,
    )
    buttons.button(QDialogButtonBox.Ok).setText("Создать")
    buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    dialog.body_layout.addWidget(title)
    dialog.body_layout.addWidget(hint)
    dialog.body_layout.addLayout(form, 1)
    dialog.body_layout.addWidget(status)
    dialog.body_layout.addWidget(buttons)
    name_input.setFocus()

    if dialog.exec() != QDialog.Accepted:
        return None

    pet = add_custom_pet(
        name_input.text(),
        str(species_input.currentData()),
        description_input.toPlainText(),
    )

    return pet


def show_pets_dialog(parent, on_change=None) -> None:
    """Открывает окно с карточками питомцев."""

    dialog = SkinDialog(
        parent,
        "Питомцы",
        min_width=900,
        min_height=660,
    )

    title = QLabel("ПИТОМЦЫ", dialog)
    title.setObjectName("dialogTitle")

    subtitle = QLabel(
        "Маленькие модели терминала по принципу тамагочи. "
        "У каждого питомца своя личность, но отвечает локальное ядро "
        "Гипериона. Закрепи одного питомца за терминалом и общайся "
        "с ним через чат.",
        dialog,
    )
    subtitle.setObjectName("dialogHint")
    subtitle.setWordWrap(True)

    scroll = QScrollArea(dialog)
    scroll.setObjectName("cardScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    holder = QWidget()
    holder.setObjectName("petsHolder")

    grid = QGridLayout(holder)
    grid.setContentsMargins(2, 2, 2, 2)
    grid.setSpacing(10)

    scroll.setWidget(holder)

    def refresh() -> None:
        """Перестраивает карточки после смены закрепления."""

        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        active_id = get_active_pet_id()

        for index, pet in enumerate(load_pets()):
            card = _build_pet_card(
                pet,
                pet["id"] == active_id,
                refresh,
                on_change,
            )
            grid.addWidget(card, index // 2, index % 2)

        grid.setRowStretch(grid.rowCount(), 1)

    create_button = QPushButton("＋ Создать питомца", dialog)
    create_button.setObjectName("activateButton")
    create_button.setCursor(Qt.ArrowCursor)
    create_button.setMinimumHeight(34)
    create_button.setMinimumWidth(190)

    close_box = QDialogButtonBox(QDialogButtonBox.Ok, dialog)
    close_box.button(QDialogButtonBox.Ok).setText("Закрыть")
    close_box.accepted.connect(dialog.accept)

    bottom = QHBoxLayout()
    bottom.setSpacing(8)
    bottom.addWidget(create_button)
    bottom.addStretch(1)
    bottom.addWidget(close_box)

    def create_pet() -> None:
        """Создаёт своего питомца и обновляет карточки."""

        if _ask_new_pet(dialog) is not None:
            refresh()

    create_button.clicked.connect(create_pet)

    refresh()

    dialog.body_layout.addWidget(title)
    dialog.body_layout.addWidget(subtitle)
    dialog.body_layout.addWidget(scroll, 1)
    dialog.body_layout.addLayout(bottom)

    show_tool_window(parent, dialog, "pets")
