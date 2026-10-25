# Giperion/terminal/ui/pets/dialog.py                                  v001
# Окно «Дроны»: список, карточка, закрепление и удаление.
# Последнее изменение: окно собрано из list_panel и card.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from terminal.core.pets import (
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
from terminal.ui.pets.card import PetCard
from terminal.ui.pets.dialogs import ask_new_pet, ask_nickname
from terminal.ui.pets.list_panel import PetListPanel


class PetsDialog(SkinDialog):
    """Список дронов и карточка выбранного."""

    def __init__(self, parent, pets: list[dict], on_change=None) -> None:
        super().__init__(
            parent,
            "Дроны",
            min_width=980,
            min_height=720,
        )

        self._parent = parent
        self._on_change = on_change
        self.pets = pets
        self.active = get_active_pet_id()

        self._build()
        self._refresh_list()

    def _build(self) -> None:
        """Собирает заголовок, две колонки и нижние кнопки."""

        title = QLabel("ДРОНЫ", self)
        title.setObjectName("dialogTitle")

        subtitle = QLabel(
            "Дроны терминала по принципу тамагочи. Слева — список, "
            "справа — карточка с характером и успехами обучения. "
            "Закрепи дрона за терминалом и общайся с ним через чат.",
            self,
        )
        subtitle.setObjectName("dialogHint")
        subtitle.setWordWrap(True)

        body = QHBoxLayout()
        body.setSpacing(12)

        self.list_panel = PetListPanel(self)
        self.card = PetCard(self)

        scroll = QScrollArea(self)
        scroll.setObjectName("cardScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(self.card)

        right = QVBoxLayout()
        right.setSpacing(6)

        right_caption = QLabel("КАРТОЧКА ДРОНА", self)
        right_caption.setObjectName("infoCaption")

        right_frame = QWidget(self)
        right_frame.setObjectName("personalityScreenFrame")

        right_frame_layout = QVBoxLayout(right_frame)
        right_frame_layout.setContentsMargins(6, 6, 6, 6)
        right_frame_layout.setSpacing(0)
        right_frame_layout.addWidget(scroll)

        right.addWidget(right_caption)
        right.addWidget(right_frame, 1)

        body.addWidget(self.list_panel, 1)
        body.addLayout(right, 2)

        self.create_button = QPushButton("＋ Создать дрона", self)
        self.create_button.setObjectName("activateButton")
        self.create_button.setCursor(Qt.ArrowCursor)
        self.create_button.setMinimumHeight(38)
        self.create_button.setMinimumWidth(190)

        self.delete_button = QPushButton("− Удалить дрона", self)
        self.delete_button.setObjectName("activateButton")
        self.delete_button.setCursor(Qt.ArrowCursor)
        self.delete_button.setMinimumHeight(38)
        self.delete_button.setMinimumWidth(190)
        self.delete_button.setEnabled(False)

        self.attach_button = QPushButton(
            "Закрепить за терминалом",
            self,
        )
        self.attach_button.setObjectName("activateButton")
        self.attach_button.setCursor(Qt.ArrowCursor)
        self.attach_button.setMinimumHeight(38)
        self.attach_button.setMinimumWidth(220)

        close_box = QDialogButtonBox(QDialogButtonBox.Ok, self)
        close_box.button(QDialogButtonBox.Ok).setText("Закрыть")
        close_box.accepted.connect(self.accept)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        buttons_row.addWidget(self.create_button)
        buttons_row.addWidget(self.delete_button)
        buttons_row.addStretch(1)
        buttons_row.addWidget(self.attach_button)
        buttons_row.addWidget(close_box)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(subtitle)
        self.body_layout.addLayout(body, 1)
        self.body_layout.addLayout(buttons_row)

        self.list_panel.selection_changed.connect(self._show_card)
        self.card.rename_requested.connect(self._rename_pet)
        self.attach_button.clicked.connect(self._toggle_attach)
        self.create_button.clicked.connect(self._create_pet)
        self.delete_button.clicked.connect(self._delete_pet)

    def _selected_pet(self) -> dict | None:
        """Дрон, выбранный в списке."""

        pet_id = self.list_panel.selected_id()

        if pet_id is None:
            return None

        return next(
            (pet for pet in self.pets if pet["id"] == pet_id),
            None,
        )

    def _refresh_list(self, keep_id: str | None = None) -> None:
        """Перечитывает дронов и перерисовывает список с карточкой."""

        self.pets = load_pets()
        self.active = get_active_pet_id()

        self.list_panel.refresh(
            self.pets,
            active=self.active,
            keep_id=keep_id,
        )
        self._show_card()

    def _show_card(self) -> None:
        """Показывает выбранного дрона и настраивает кнопки."""

        pet = self._selected_pet()

        self.card.show_pet(pet, self.active)
        self.attach_button.setEnabled(pet is not None)
        self.delete_button.setEnabled(
            pet is not None and bool(pet.get("custom"))
        )

        if pet is None:
            self.attach_button.setText("Закрепить за терминалом")

            return

        self.attach_button.setText(
            "Открепить"
            if pet["id"] == self.active
            else "Закрепить за терминалом"
        )

    def _toggle_attach(self) -> None:
        """Закрепляет выбранного дрона или освобождает его."""

        pet = self._selected_pet()

        if pet is None:
            return

        if pet["id"] == self.active:
            set_active_pet_id("")
        else:
            set_active_pet_id(pet["id"])

        if self._on_change is not None:
            self._on_change()

        self._refresh_list(keep_id=pet["id"])

    def _create_pet(self) -> None:
        """Создаёт своего дрона."""

        pet = ask_new_pet(self)

        if pet is None:
            return

        self._refresh_list(keep_id=pet["id"])

    def _rename_pet(self) -> None:
        """Меняет кличку выбранного дрона."""

        pet = self._selected_pet()

        if pet is None:
            return

        nickname = ask_nickname(self, pet)

        if nickname is None:
            return

        if set_pet_nickname(pet["id"], nickname) is None:
            return

        if self._on_change is not None:
            self._on_change()

        self._refresh_list(keep_id=pet["id"])

    def _delete_pet(self) -> None:
        """Удаляет своего дрона из списка."""

        pet = self._selected_pet()

        if pet is None or not pet.get("custom"):
            return

        confirm = ConfirmDialog(
            self,
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

        if self._on_change is not None:
            self._on_change()

        self._refresh_list()


def show_pets_dialog(parent, on_change=None) -> None:
    """Открывает список дронов и карточку выбранного дрона."""

    pets = load_pets()

    if not pets:
        return

    dialog = PetsDialog(parent, pets, on_change)
    show_tool_window(parent, dialog, "pets")
