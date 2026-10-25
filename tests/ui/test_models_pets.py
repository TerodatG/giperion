# Giperion/tests/ui/test_models_pets.py                              v001
# Модели, свои модели, дроны и клички.
# Последнее изменение: вынесено из test_gui_smoke.



def test_model_groups_switch_disables_models(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """Галочки групп выключают модели, сенат и компаньонов."""

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QLabel,
        QListWidget,
        QPushButton,
        QTabBar,
    )

    from terminal.core import model_files, model_settings
    from terminal.core.model_catalog import CONFERENCE_GROUP

    monkeypatch.setattr(
        model_files,
        "SETTINGS_FILE",
        tmp_path / "model_settings.json",
    )

    go_id = "go-deepseek-v4.1-flash"

    assert model_settings.set_conference_member(go_id, True)

    window.open_models_dialog()

    dialog = window.window._tool_windows["models"]

    boxes = {
        box.text(): box
        for box in dialog.findChildren(QCheckBox)
    }

    assert boxes["Бесплатные модели"].isChecked()
    assert boxes["Модели Go"].isChecked()

    tabs = dialog.findChild(QTabBar)
    view = dialog.findChild(QListWidget, "modelsView")

    def row_ids() -> list[str]:
        """Идентификаторы строк текущей закладки."""

        return [
            view.item(index).data(Qt.UserRole)
            for index in range(view.count())
        ]

    senate = next(
        index
        for index in range(tabs.count())
        if tabs.tabData(index) == CONFERENCE_GROUP
    )
    tabs.setCurrentIndex(senate)
    QApplication.processEvents()

    assert go_id in row_ids()

    boxes["Модели Go"].setChecked(False)
    QApplication.processEvents()

    assert go_id not in row_ids()
    assert go_id not in model_settings.load_conference_ids()

    other = next(
        index
        for index in range(tabs.count())
        if tabs.tabData(index) == "other"
    )
    tabs.setCurrentIndex(other)
    QApplication.processEvents()

    for index in range(view.count()):
        if view.item(index).data(Qt.UserRole) == go_id:
            view.setCurrentRow(index)

            break

    QApplication.processEvents()

    status = dialog.findChild(QLabel, "modelStatus")
    activate = dialog.findChild(QPushButton, "activateButton")

    assert "недоступна" in status.text()
    assert "Модели Go" in status.text()
    assert activate.isEnabled() is False
    assert "· недоступна" in view.currentItem().text()

    boxes["Модели Go"].setChecked(True)
    QApplication.processEvents()

    assert go_id in model_settings.load_conference_ids()

    dialog.close()


def test_pet_nickname_can_be_changed_in_dialog(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """В окне «Дроны» кличка меняется кнопкой."""

    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from terminal.core import pets
    from terminal.ui.pets import dialog as pets_dialog_module

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )
    monkeypatch.setattr(
        pets_dialog_module,
        "ask_nickname",
        lambda parent, pet: "Бублик",
    )

    window.open_pets_dialog()

    dialog = window.window._tool_windows["pets"]

    texts = [label.text() for label in dialog.findChildren(QLabel)]

    # В карточке нет дубля вида, а кличка по умолчанию не задана.
    assert texts.count("Кибер паук") == 1
    assert any("КЛИЧКА: не задана" in text for text in texts)

    button = next(
        item
        for item in dialog.findChildren(QPushButton)
        if item.text() == "✎ Переименовать"
    )

    button.click()
    QApplication.processEvents()

    loaded = {pet["id"]: pet for pet in pets.load_pets()}

    assert loaded["cyber-spider"]["nickname"] == "Бублик"
    assert loaded["cyber-spider"]["name"] == "Кибер паук"

    texts = [label.text() for label in dialog.findChildren(QLabel)]

    assert any("КЛИЧКА: Бублик" in text for text in texts)

    dialog.close()


def test_own_model_can_be_deleted(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """В закладке «Свои» модель удаляется из каталога."""

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QListWidget,
        QPushButton,
        QTabBar,
    )

    from terminal.core import model_files, model_registry
    from terminal.ui import dialogs_base

    monkeypatch.setattr(
        model_files,
        "CUSTOM_MODELS_FILE",
        tmp_path / "custom_models.json",
    )
    monkeypatch.setattr(
        model_files,
        "SETTINGS_FILE",
        tmp_path / "model_settings.json",
    )
    monkeypatch.setattr(
        dialogs_base.ConfirmDialog,
        "exec",
        lambda self: QDialog.Accepted,
    )

    model = model_registry.add_custom_model("Своя", "Local")

    assert model is not None

    window.open_models_dialog()

    dialog = window.window._tool_windows["models"]

    tabs = dialog.findChild(QTabBar)
    own = next(
        index
        for index in range(tabs.count())
        if tabs.tabData(index) == "own"
    )
    tabs.setCurrentIndex(own)
    QApplication.processEvents()

    view = dialog.findChild(QListWidget, "modelsView")
    row = next(
        index
        for index in range(view.count())
        if view.item(index).data(Qt.UserRole) == model["id"]
    )
    view.setCurrentRow(row)
    QApplication.processEvents()

    delete = next(
        button
        for button in dialog.findChildren(QPushButton)
        if button.text() == "− Удалить модель"
    )

    assert delete.isVisible()
    assert delete.isEnabled()

    delete.click()
    QApplication.processEvents()

    ids = [
        item["id"] for item in model_registry.load_models()
    ]

    assert model["id"] not in ids

    dialog.close()


def test_custom_drone_can_be_deleted(
    window,
    tmp_path,
    monkeypatch,
) -> None:
    """В окне «Дроны» своего дрона можно удалить."""

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QDialog,
        QListWidget,
        QPushButton,
    )

    from terminal.core import pets
    from terminal.ui import dialogs_base

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )
    monkeypatch.setattr(
        dialogs_base.ConfirmDialog,
        "exec",
        lambda self: QDialog.Accepted,
    )

    custom = pets.add_custom_pet("Шарик", "spider")

    assert custom is not None

    window.open_pets_dialog()

    dialog = window.window._tool_windows["pets"]

    delete = next(
        button
        for button in dialog.findChildren(QPushButton)
        if button.text() == "− Удалить дрона"
    )

    # По умолчанию выбран базовый дрон — удалять его нельзя.
    assert delete.isEnabled() is False

    view = dialog.findChild(QListWidget, "modelsView")

    for row in range(view.count()):
        if view.item(row).data(Qt.UserRole) == custom["id"]:
            view.setCurrentRow(row)

            break

    QApplication.processEvents()

    assert delete.isEnabled() is True

    delete.click()
    QApplication.processEvents()

    assert pets.get_pet(custom["id"]) is None

    dialog.close()
