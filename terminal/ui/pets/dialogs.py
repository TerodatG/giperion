# Giperion/terminal/ui/pets/dialogs.py                                 v001
# Небольшие окна дронов: создание и смена клички.
# Последнее изменение: вынесено из pets_dialog.

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
)

from terminal.core.pets import SPECIES_TITLES, add_custom_pet
from terminal.ui.dialogs_base import SkinDialog


def ask_new_pet(parent) -> dict | None:
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


def ask_nickname(parent, pet: dict) -> str | None:
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
