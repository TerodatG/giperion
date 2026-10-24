# Giperion/app/ui/add_model_dialog.py                              v001
# Форма добавления своей модели в каталог.
# Последнее изменение: вынесено из models_dialog.

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from terminal.core.model_registry import add_custom_model


def show_add_model_dialog(parent) -> dict | None:
    """Спрашивает данные своей модели и добавляет её в каталог."""

    dialog = QDialog(parent)
    dialog.setWindowTitle("Своя модель")
    dialog.setMinimumSize(500, 360)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(16, 14, 16, 12)
    layout.setSpacing(8)

    title = QLabel("НОВАЯ МОДЕЛЬ", dialog)
    title.setObjectName("dialogTitle")

    hint = QLabel(
        "Опиши модель, которой нет в списке. Она появится "
        "на закладке «Свои», и её можно будет активировать.",
        dialog,
    )
    hint.setObjectName("dialogHint")
    hint.setWordWrap(True)

    form = QFormLayout()
    form.setSpacing(6)

    name_input = QLineEdit(dialog)
    name_input.setPlaceholderText("Например, Qwen 3")

    provider_input = QLineEdit(dialog)
    provider_input.setPlaceholderText("Например, Alibaba")

    url_input = QLineEdit(dialog)
    url_input.setPlaceholderText("https://…")

    description_input = QLineEdit(dialog)
    description_input.setPlaceholderText("Чем занимается модель")

    context_input = QSpinBox(dialog)
    context_input.setRange(0, 2_000_000)
    context_input.setValue(32000)
    context_input.setSingleStep(1000)
    context_input.setSuffix(" токенов")

    budget_input = QSpinBox(dialog)
    budget_input.setRange(0, 1_000_000_000)
    budget_input.setValue(1_000_000)
    budget_input.setSingleStep(100_000)
    budget_input.setSuffix(" токенов")

    form.addRow("Название", name_input)
    form.addRow("Поставщик", provider_input)
    form.addRow("Сайт", url_input)
    form.addRow("Описание", description_input)
    form.addRow("Лимит контекста", context_input)
    form.addRow("Бюджет токенов", budget_input)

    created = {}

    buttons = QDialogButtonBox(
        QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
        dialog,
    )
    buttons.button(QDialogButtonBox.Ok).setText("Добавить")
    buttons.button(QDialogButtonBox.Cancel).setText("Отмена")

    def accept() -> None:
        """Проверяет название и сохраняет модель."""

        model = add_custom_model(
            name_input.text(),
            provider_input.text(),
            url_input.text(),
            description_input.text(),
            context_input.value(),
            budget_input.value(),
        )

        if model is None:
            QMessageBox.warning(
                dialog,
                "Своя модель",
                "У модели должно быть название.",
            )

            return

        created["model"] = model
        dialog.accept()

    buttons.accepted.connect(accept)
    buttons.rejected.connect(dialog.reject)

    layout.addWidget(title)
    layout.addWidget(hint)
    layout.addLayout(form)
    layout.addStretch(1)
    layout.addWidget(buttons)

    dialog.exec()

    return created.get("model")
