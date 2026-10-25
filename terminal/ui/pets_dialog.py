# Giperion/terminal/ui/pets_dialog.py                                v007
# Окно «Дроны»: список дронов, карточка и смена клички.
# Последнее изменение: удаление своего дрона.

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
    remove_custom_pet,
    set_active_pet_id,
    set_pet_nickname,
)
from terminal.ui.dialogs_base import (
    ConfirmDialog,
    SkinDialog,
    show_tool_window,
)


def _ask_new_pet(parent) -> dict | None:
    """Спрашивает имя и вид нового дрона."""

    dialog = SkinDialog(
        parent,
        "Новый дрон",
        min_width=560,
        min_height=390,
    )

    title = QLabel("НОВЫЙ ДРОН", dialog)
    title.setObjectName("dialogTitle")

    hint = QLabel(
        "Дрон получает базовый шаблон личности. Полноценная "
        "модель для него не нужна: общение идёт через терминал.",
        dialog,
    )
    hint.setObjectName("dialogHint")
    hint.setWordWrap(True)

    name_input = QLineEdit(dialog)
    name_input.setObjectName("petInput")
    name_input.setPlaceholderText("Имя дрона")
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


def _ask_nickname(parent, pet: dict) -> str | None:
    """Спрашивает новую кличку дрона."""

    dialog = SkinDialog(
        parent,
        "Кличка дрона",
        min_width=540,
        min_height=260,
    )

    title = QLabel("КЛИЧКА ДРОНА", dialog)
    title.setObjectName("dialogTitle")

    hint = QLabel(
        f"Как звать дрона «{pet['name']}»? Кличка видна в списке "
        "дронов, в чате и в подсказке поля ввода. Вид и успехи "
        "обучения не меняются.",
        dialog,
    )
    hint.setObjectName("dialogHint")
    hint.setWordWrap(True)

    nickname_input = QLineEdit(dialog)
    nickname_input.setObjectName("petInput")
    nickname_input.setMaxLength(40)
    nickname_input.setText(pet.get("nickname") or pet["name"])
    nickname_input.selectAll()

    buttons = QDialogButtonBox(
        QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
        dialog,
    )
    buttons.button(QDialogButtonBox.Ok).setText("Сохранить")
    buttons.button(QDialogButtonBox.Cancel).setText("Отмена")

    def update_ok() -> None:
        """Не разрешает сохранить пустую кличку."""

        buttons.button(QDialogButtonBox.Ok).setEnabled(
            bool(nickname_input.text().strip())
        )

    def accept_if_valid() -> None:
        """Сохраняет кличку по Enter, если она не пустая."""

        if nickname_input.text().strip():
            dialog.accept()

    nickname_input.textChanged.connect(update_ok)
    nickname_input.returnPressed.connect(accept_if_valid)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)

    dialog.body_layout.addWidget(title)
    dialog.body_layout.addWidget(hint)
    dialog.body_layout.addWidget(nickname_input)
    dialog.body_layout.addStretch(1)
    dialog.body_layout.addWidget(buttons)

    update_ok()
    nickname_input.setFocus()

    if dialog.exec() != QDialog.Accepted:
        return None

    return nickname_input.text().strip()


def show_pets_dialog(parent, on_change=None) -> None:
    """Открывает список дронов и карточку выбранного дрона."""

    pets = load_pets()

    if not pets:
        return

    active_id = get_active_pet_id()
    selected_id = active_id or pets[0]["id"]

    dialog = SkinDialog(
        parent,
        "Дроны",
        min_width=980,
        min_height=720,
    )

    layout = dialog.body_layout

    title = QLabel("ДРОНЫ", dialog)
    title.setObjectName("dialogTitle")

    subtitle = QLabel(
        "Дроны терминала по принципу тамагочи. Слева — список, "
        "справа — карточка с характером и успехами обучения. "
        "Закрепи дрона за терминалом и общайся с ним через чат.",
        dialog,
    )
    subtitle.setObjectName("dialogHint")
    subtitle.setWordWrap(True)

    body = QHBoxLayout()
    body.setSpacing(12)

    # --- Слева: список дронов ---
    left = QVBoxLayout()
    left.setSpacing(6)

    left_caption = QLabel("СПИСОК ДРОНОВ", dialog)
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

    # --- Справа: карточка дрона ---
    right = QVBoxLayout()
    right.setSpacing(6)

    right_caption = QLabel("КАРТОЧКА ДРОНА", dialog)
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

    nickname_label = QLabel(card)
    nickname_label.setObjectName("modelNickname")
    nickname_label.setWordWrap(True)

    rename_button = QPushButton("✎ Переименовать", card)
    rename_button.setObjectName("aiParamsButton")
    rename_button.setCursor(Qt.ArrowCursor)
    rename_button.setFocusPolicy(Qt.NoFocus)
    rename_button.setToolTip("Изменить кличку дрона")

    nickname_row = QHBoxLayout()
    nickname_row.setContentsMargins(0, 0, 0, 0)
    nickname_row.setSpacing(8)
    nickname_row.addWidget(nickname_label, 1)
    nickname_row.addWidget(rename_button, 0, Qt.AlignRight)

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
    card_layout.addLayout(nickname_row)
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
    create_button = QPushButton("＋ Создать дрона", dialog)
    create_button.setObjectName("activateButton")
    create_button.setCursor(Qt.ArrowCursor)
    create_button.setMinimumHeight(38)
    create_button.setMinimumWidth(190)

    delete_button = QPushButton("− Удалить дрона", dialog)
    delete_button.setObjectName("activateButton")
    delete_button.setCursor(Qt.ArrowCursor)
    delete_button.setMinimumHeight(38)
    delete_button.setMinimumWidth(190)
    delete_button.setEnabled(False)

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
    buttons_row.addWidget(delete_button)
    buttons_row.addStretch(1)
    buttons_row.addWidget(attach_button)
    buttons_row.addWidget(close_box)

    state = {
        "pets": pets,
        "active": active_id,
    }

    def selected_pet() -> dict | None:
        """Дрон, выбранный в списке."""

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
        """Заполняет карточку выбранного дрона."""

        pet = selected_pet()
        attach_button.setEnabled(pet is not None)
        rename_button.setEnabled(pet is not None)
        delete_button.setEnabled(
            pet is not None and bool(pet.get("custom"))
        )

        if pet is None:
            name_label.setText("Выбери дрона")
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

        nickname = pet.get("nickname") or ""

        name_label.setText(pet["name"])
        nickname_label.setText(
            f"КЛИЧКА: {nickname}" if nickname else "КЛИЧКА: не задана"
        )
        nickname_label.setStyleSheet(
            "" if nickname else "color: #6f7d72;"
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
        """Перерисовывает список, сохраняя выбранного дрона."""

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
            species_title = pet.get("species_title") or SPECIES_TITLES.get(
                pet.get("species", "custom"),
                SPECIES_TITLES["custom"],
            )

            item = QListWidgetItem(
                f"{pet.get('symbol') or '🛠️'}  "
                f"{pet.get('nickname') or pet['name']}\n"
                f"{species_title}"
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
        """Закрепляет выбранного дрона или освобождает его."""

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
        """Создаёт своего дрона."""

        pet = _ask_new_pet(dialog)

        if pet is None:
            return

        refresh_list(keep_id=pet["id"])
        show_card()

    def rename_pet() -> None:
        """Меняет кличку выбранного дрона."""

        pet = selected_pet()

        if pet is None:
            return

        nickname = _ask_nickname(dialog, pet)

        if nickname is None:
            return

        if set_pet_nickname(pet["id"], nickname) is None:
            return

        if on_change is not None:
            on_change()

        refresh_list(keep_id=pet["id"])
        show_card()

    def delete_pet() -> None:
        """Удаляет своего дрона из списка."""

        pet = selected_pet()

        if pet is None or not pet.get("custom"):
            return

        confirm = ConfirmDialog(
            dialog,
            "Удалить дрона",
            f"Удалить дрона "
            f"«{pet.get('nickname') or pet['name']}»? "
            "Его успехи обучения тоже исчезнут.",
            "Удалить",
        )

        if confirm.exec() != QDialog.Accepted:
            return

        if not remove_custom_pet(pet["id"]):
            return

        if on_change is not None:
            on_change()

        refresh_list()
        show_card()

    view.currentItemChanged.connect(
        lambda current, previous: show_card()
    )
    attach_button.clicked.connect(toggle_attach)
    create_button.clicked.connect(create_pet)
    rename_button.clicked.connect(rename_pet)
    delete_button.clicked.connect(delete_pet)

    refresh_list()
    show_card()

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addLayout(body, 1)
    layout.addLayout(buttons_row)

    show_tool_window(parent, dialog, "pets")
