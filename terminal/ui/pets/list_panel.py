# Giperion/terminal/ui/pets/list_panel.py                              v001
# Левая колонка окна «Дроны»: список с видом, уровнем и статусом.
# Последнее изменение: вынесено из pets_dialog.

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from terminal.core.pets import SPECIES_TITLES


class PetListPanel(QWidget):
    """Список дронов и подпись над ним."""

    selection_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        caption = QLabel("СПИСОК ДРОНОВ", self)
        caption.setObjectName("infoCaption")

        frame = QWidget(self)
        frame.setObjectName("personalityScreenFrame")

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(6, 6, 6, 6)
        frame_layout.setSpacing(0)

        self.view = QListWidget(self)
        self.view.setObjectName("modelsView")
        self.view.setSelectionMode(QListWidget.SingleSelection)
        self.view.setUniformItemSizes(True)
        self.view.setMinimumWidth(250)

        frame_layout.addWidget(self.view)
        layout.addWidget(caption)
        layout.addWidget(frame, 1)

        self.view.currentItemChanged.connect(
            lambda current, previous: self.selection_changed.emit()
        )

    def selected_id(self) -> str | None:
        """Идентификатор выбранного дрона."""

        item = self.view.currentItem()

        if item is None:
            return None

        return item.data(Qt.UserRole)

    def refresh(
        self,
        pets: list[dict],
        *,
        active: str,
        keep_id: str | None = None,
    ) -> None:
        """Перерисовывает список, сохраняя выбранного дрона."""

        current = keep_id or self.selected_id() or active

        self.view.blockSignals(True)
        self.view.clear()

        for pet in pets:
            status = (
                "закреплён" if pet["id"] == active else "свободен"
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
                self.view,
            )
            item.setData(Qt.UserRole, pet["id"])
            item.setSizeHint(QSize(0, 56))

        row = 0

        for index in range(self.view.count()):
            if self.view.item(index).data(Qt.UserRole) == current:
                row = index

                break

        if self.view.count():
            self.view.setCurrentRow(row)
            self.view.doItemsLayout()

        self.view.blockSignals(False)

    def select_id(self, pet_id: str) -> None:
        """Выбирает строку по идентификатору."""

        for row in range(self.view.count()):
            if self.view.item(row).data(Qt.UserRole) == pet_id:
                self.view.setCurrentRow(row)

                return
