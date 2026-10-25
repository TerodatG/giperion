# Giperion/terminal/ui/pets_dialog.py                                v003
# Окно «Питомцы»: список питомцев и карточка с успехами обучения.
# Последнее изменение: ровные строки списка без наезда выделения.

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
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


def _ask_new_pet(parent) -> dict | None:
    """Спрашивает имя и вид нового питомца."""

    dialog = SkinDialog(
        parent,
        "Новый питомец",
        min_width=560,
        min_height=390,
    )

    title = QLabel("НОВЫЙ ПИТОМЕЦ", dialog)
    title.setObjectName("dialogTitle")

    hint = QLabel(
        "Питомец получает базовый шаблон личности. Полноценная "
        "модель для него не нужна: общение идёт через терминал.",
        dialog,
    )
    hint.setObjectName("dialogHint")
    hint.setWordWrap(True)

    name_input = QLineEdit(dialog)
    name_input.setObjectName("petInput")
    name_input.setPlaceholderText("Имя питомца")
    name_input.setMaxLength(40)

    species_input = QComboBox(dialog)
    species_input.setObjectName("petCombo")

    for key, value in SPECIES_TITLES.items():
        species_input.addItem(value, key)

    description_input = QPlainTextEdit(dialog)
    description_input.setObjectName("petInput")
    description_input.setPlaceholderText(
        "Короткое описание характера (необязательно)"
    )
    description_input.setMaximumHeight(96)

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

    return add_custom_pet(
        name_input.text(),
        str(species_input.currentData()),
        description_input.toPlainText(),
    )


def show_pets_dialog(parent, on_change=None) -> None:
    """Открывает список питомцев и карточку выбранного питомца."""

    pets = load_pets()

    if not pets:
        return

    active_id = get_active_pet_id()
    selected_id = active_id or pets[0]["id"]

    dialog = SkinDialog(
        parent,
        "Питомцы",
        min_width=980,
        min_height=720,
    )

    layout = dialog.body_layout

    title = QLabel("ПИТОМЦЫ", dialog)
    title.setObjectName("dialogTitle")

    subtitle = QLabel(
        "Маленькие обитатели терминала по принципу тамагочи. "
        "Слева — список, справа — карточка с характером и успехами "
        "обучения. Закрепи питомца за терминалом и общайся с ним "
        "через чат.",
        dialog,
    )
    subtitle.setObjectName("dialogHint")
    subtitle.setWordWrap(True)

    body = QHBoxLayout()
    body.setSpacing(12)

    # --- Слева: список питомцев ---
    left = QVBoxLayout()
    left.setSpacing(6)

    left_caption = QLabel("СПИСОК ПИТОМЦЕВ", dialog)
    left_caption.setObjectName("infoCaption")

    left_frame = QWidget(dialog)
    left_frame.setObjectName("personalityScreenFrame")

    left_frame_layout = QVBoxLayout(left_frame)
    left_frame_layout.setContentsMargins(6, 6, 6, 6)
    left_frame_layout.setSpacing(0)

    view = QListWidget(dialog)
    view.setObjectName("modelsView")
    view.setSelectionMode(QListWidget.SingleSelection)
    view.setUniformItemSizes(True)
    view.setMinimumWidth(250)

    left_frame_layout.addWidget(view)
    left.addWidget(left_caption)
    left.addWidget(left_frame, 1)

    # --- Справа: карточка питомца ---
    right = QVBoxLayout()
    right.setSpacing(6)

    right_caption = QLabel("КАРТОЧКА ПИТОМЦА", dialog)
    right_caption.setObjectName("infoCaption")

    right_frame = QWidget(dialog)
    right_frame.setObjectName("personalityScreenFrame")

    right_frame_layout = QVBoxLayout(right_frame)
    right_frame_layout.setContentsMargins(6, 6, 6, 6)
    right_frame_layout.setSpacing(0)

    scroll = QScrollArea(dialog)
    scroll.setObjectName("cardScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    card = QWidget()
    card.setObjectName("modelCard")

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(16, 14, 16, 14)
    card_layout.setSpacing(10)

    name_label = QLabel(card)
    name_label.setObjectName("modelName")
    name_label.setWordWrap(True)

    type_label = QLabel(card)
    type_label.setObjectName("modelProvider")

    nickname_label = QLabel(card)
    nickname_label.setObjectName("modelNickname")
    nickname_label.setWordWrap(True)

    identity = QHBoxLayout()
    identity.setSpacing(12)

    avatar_label = QLabel(card)
    avatar_label.setObjectName("modelAvatar")
    avatar_label.setFixedSize(96, 96)
    avatar_label.setAlignment(Qt.AlignCenter)

    traits_widget = QWidget(card)
    traits_layout = QVBoxLayout(traits_widget)
    traits_layout.setContentsMargins(0, 0, 0, 0)
    traits_layout.setSpacing(3)

    identity.addWidget(avatar_label)
    identity.addWidget(traits_widget, 1)

    description_label = QLabel(card)
    description_label.setObjectName("modelDescription")
    description_label.setWordWrap(True)
    description_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

    training_caption = QLabel("УСПЕХИ ОБУЧЕНИЯ", card)
    training_caption.setObjectName("infoCaption")

    training_screen = QWidget(card)
    training_screen.setObjectName("petTrainingScreen")

    training_layout = QVBoxLayout(training_screen)
    training_layout.setContentsMargins(10, 8, 10, 8)
    training_layout.setSpacing(4)

    training_level = QLabel(training_screen)
    training_level.setObjectName("petTrainingLine")

    training_conversations = QLabel(training_screen)
    training_conversations.setObjectName("petTrainingLine")

    training_learned = QLabel(training_screen)
    training_learned.setObjectName("petTrainingLine")

    training_experience = QLabel(training_screen)
    training_experience.setObjectName("petTrainingLine")

    training_bar = QProgressBar(training_screen)
    training_bar.setObjectName("petTrainingBar")
    training_bar.setRange(0, 100)
    training_bar.setTextVisible(False)
    training_bar.setFixedHeight(10)

    training_layout.addWidget(training_level)
    training_layout.addWidget(training_conversations)
    training_layout.addWidget(training_learned)
    training_layout.addWidget(training_experience)
    training_layout.addWidget(training_bar)

    traits_caption = QLabel("ХАРАКТЕР · ОЦЕНКА 0–5", card)
    traits_caption.setObjectName("infoCaption")

    speech_caption = QLabel("МАНЕРА ОБЩЕНИЯ", card)
    speech_caption.setObjectName("infoCaption")

    speech_label = QLabel(card)
    speech_label.setObjectName("modelDescription")
    speech_label.setWordWrap(True)

    status_label = QLabel(card)
    status_label.setObjectName("modelStatus")
    status_label.setWordWrap(True)

    card_layout.addWidget(name_label)
    card_layout.addWidget(type_label)
    card_layout.addWidget(nickname_label)
    card_layout.addWidget(traits_caption)
    card_layout.addLayout(identity)
    card_layout.addWidget(description_label)
    card_layout.addWidget(training_caption)
    card_layout.addWidget(training_screen)
    card_layout.addWidget(speech_caption)
    card_layout.addWidget(speech_label)
    card_layout.addStretch(1)
    card_layout.addWidget(status_label)

    scroll.setWidget(card)

    right_frame_layout.addWidget(scroll)
    right.addWidget(right_caption)
    right.addWidget(right_frame, 1)

    body.addLayout(left, 1)
    body.addLayout(right, 2)

    # --- Нижняя строка ---
    create_button = QPushButton("＋ Создать питомца", dialog)
    create_button.setObjectName("activateButton")
    create_button.setCursor(Qt.ArrowCursor)
    create_button.setMinimumHeight(38)
    create_button.setMinimumWidth(190)

    attach_button = QPushButton("Закрепить за терминалом", dialog)
    attach_button.setObjectName("activateButton")
    attach_button.setCursor(Qt.ArrowCursor)
    attach_button.setMinimumHeight(38)
    attach_button.setMinimumWidth(220)

    close_box = QDialogButtonBox(QDialogButtonBox.Ok, dialog)
    close_box.button(QDialogButtonBox.Ok).setText("Закрыть")
    close_box.accepted.connect(dialog.accept)

    buttons_row = QHBoxLayout()
    buttons_row.setSpacing(8)
    buttons_row.addWidget(create_button)
    buttons_row.addStretch(1)
    buttons_row.addWidget(attach_button)
    buttons_row.addWidget(close_box)

    state = {
        "pets": pets,
        "active": active_id,
    }

    def selected_pet() -> dict | None:
        """Питомец, выбранный в списке."""

        item = view.currentItem()

        if item is None:
            return None

        pet_id = item.data(Qt.UserRole)

        return next(
            (
                pet
                for pet in state["pets"]
                if pet["id"] == pet_id
            ),
            None,
        )

    def fill_traits(pet: dict | None) -> None:
        """Перерисовывает шкалы характера."""

        while traits_layout.count():
            item = traits_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if pet is None:
            return

        traits = pet.get("traits") or {}

        for trait_name, value in traits.items():
            row = QWidget(traits_widget)

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            name = QLabel(str(trait_name), row)
            name.setObjectName("strengthName")
            name.setFixedWidth(120)

            bar = QProgressBar(row)
            bar.setObjectName("strengthBar")
            bar.setRange(0, 5)
            bar.setValue(int(value))
            bar.setTextVisible(False)
            bar.setFixedHeight(10)

            score = QLabel(str(value), row)
            score.setObjectName("strengthValue")
            score.setFixedWidth(14)

            row_layout.addWidget(name)
            row_layout.addWidget(bar, 1)
            row_layout.addWidget(score)
            traits_layout.addWidget(row)

    def show_card() -> None:
        """Заполняет карточку выбранного питомца."""

        pet = selected_pet()
        attach_button.setEnabled(pet is not None)

        if pet is None:
            name_label.setText("Выбери питомца")
            type_label.setText("")
            nickname_label.setText("")
            description_label.setText("")
            speech_label.setText("")
            status_label.setText("")
            avatar_label.setText("")
            training_level.setText("")
            training_conversations.setText("")
            training_learned.setText("")
            training_experience.setText("")
            training_bar.setValue(0)
            fill_traits(None)

            return

        progress = pet.get("progress") or {}
        level = int(progress.get("level", 1) or 1)
        experience = int(progress.get("experience", 0) or 0)
        conversations = int(
            progress.get("conversations", 0) or 0
        )
        learned = int(progress.get("learned_phrases", 0) or 0)

        name_label.setText(pet["name"])
        type_label.setText(
            pet.get("species_title")
            or SPECIES_TITLES.get(
                pet.get("species", "custom"),
                SPECIES_TITLES["custom"],
            )
        )
        nickname_label.setText(
            f"КЛИЧКА: {pet.get('nickname') or pet['name']}"
        )
        description_label.setText(
            pet.get("description")
            or "Описание пока не заполнено."
        )
        speech_label.setText(pet.get("speech") or "")
        avatar_label.setText(pet.get("symbol") or "🐾")

        training_level.setText(f"Уровень: {level}")
        training_conversations.setText(
            f"Разговоров: {conversations}"
        )
        training_learned.setText(
            f"Выучено фраз: {learned}"
        )
        training_experience.setText(
            f"Опыт: {experience} · до следующего уровня "
            f"{100 - experience % 100}"
        )
        training_bar.setValue(experience % 100)

        fill_traits(pet)

        is_active = pet["id"] == state["active"]

        status_label.setText(
            "Статус: закреплён за терминалом."
            if is_active
            else "Статус: свободен."
        )
        attach_button.setText(
            "Открепить"
            if is_active
            else "Закрепить за терминалом"
        )

    def refresh_list(keep_id: str | None = None) -> None:
        """Перерисовывает список, сохраняя выбранного питомца."""

        state["pets"] = load_pets()
        state["active"] = get_active_pet_id()

        view.blockSignals(True)
        view.clear()

        for pet in state["pets"]:
            status = (
                "закреплён"
                if pet["id"] == state["active"]
                else "свободен"
            )
            level = int(
                (pet.get("progress") or {}).get("level", 1) or 1
            )
            item = QListWidgetItem(
                f"{pet.get('symbol') or '🐾'}  {pet['name']}\n"
                f"{pet.get('species_title') or SPECIES_TITLES['custom']}"
                f" · ур. {level} · {status}",
                view,
            )
            item.setData(Qt.UserRole, pet["id"])
            item.setSizeHint(QSize(0, 56))

        target_id = keep_id or selected_id or state["active"]
        row = 0

        for index in range(view.count()):
            if view.item(index).data(Qt.UserRole) == target_id:
                row = index

                break

        if view.count():
            view.setCurrentRow(row)
            view.doItemsLayout()

        view.blockSignals(False)

    def toggle_attach() -> None:
        """Закрепляет выбранного питомца или освобождает его."""

        pet = selected_pet()

        if pet is None:
            return

        if pet["id"] == state["active"]:
            set_active_pet_id("")
        else:
            set_active_pet_id(pet["id"])

        if on_change is not None:
            on_change()

        refresh_list(keep_id=pet["id"])
        show_card()

    def create_pet() -> None:
        """Создаёт своего питомца."""

        pet = _ask_new_pet(dialog)

        if pet is None:
            return

        refresh_list(keep_id=pet["id"])
        show_card()

    view.currentItemChanged.connect(
        lambda current, previous: show_card()
    )
    attach_button.clicked.connect(toggle_attach)
    create_button.clicked.connect(create_pet)

    refresh_list()
    show_card()

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addLayout(body, 1)
    layout.addLayout(buttons_row)

    show_tool_window(parent, dialog, "pets")
