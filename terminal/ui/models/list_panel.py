# Giperion/terminal/ui/models/list_panel.py                            v001
# Левая колонка окна «Модель»: закладки, список и кнопки «Своих».
# Последнее изменение: вынесено из show_models_dialog.

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from terminal.core.conference_roster import (
    MAX_CONFERENCE_MODELS,
    senator_title,
)
from terminal.core.model_catalog import (
    COMPANION_GROUP,
    CONFERENCE_GROUP,
    MODEL_GROUPS,
)
from terminal.ui.model_list_widgets import (
    SENATOR_ICON_ROLE,
    ModelListDelegate,
)
from terminal.ui.value_text import build_model_item_text


class ModelListPanel(QWidget):
    """Закладки и список моделей; карточка живёт справа."""

    group_changed = Signal(int)
    selection_changed = Signal()
    add_requested = Signal()
    delete_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.tabs = QTabBar(self)
        self.tabs.setObjectName("modelsTabs")
        self.tabs.setExpanding(False)
        self.tabs.setDrawBase(False)

        for group_key, group_label in MODEL_GROUPS:
            index = self.tabs.addTab(group_label)
            self.tabs.setTabData(index, group_key)

        self.view = QListWidget(self)
        self.view.setObjectName("modelsView")
        self.view.setSelectionMode(QListWidget.SingleSelection)
        self.view.setItemDelegate(ModelListDelegate(self.view))
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setTextElideMode(Qt.ElideRight)

        list_frame = QWidget(self)
        list_frame.setObjectName("modelScreenFrame")

        list_frame_layout = QVBoxLayout(list_frame)
        list_frame_layout.setContentsMargins(6, 6, 6, 6)
        list_frame_layout.setSpacing(0)
        list_frame_layout.addWidget(self.view)

        self.add_button = QPushButton("+ Добавить модель", self)
        self.add_button.setObjectName("addModelButton")
        self.add_button.setCursor(Qt.ArrowCursor)
        self.add_button.setVisible(False)

        self.delete_button = QPushButton("− Удалить модель", self)
        self.delete_button.setObjectName("addModelButton")
        self.delete_button.setCursor(Qt.ArrowCursor)
        self.delete_button.setVisible(False)
        self.delete_button.setEnabled(False)

        self.empty_hint = QLabel("Своих моделей пока нет", self)
        self.empty_hint.setObjectName("dialogHint")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setVisible(False)

        layout.addWidget(self.tabs)
        layout.addWidget(list_frame, 1)

        own_buttons = QHBoxLayout()
        own_buttons.setContentsMargins(0, 0, 0, 0)
        own_buttons.setSpacing(8)
        own_buttons.addWidget(self.add_button)
        own_buttons.addStretch(1)
        own_buttons.addWidget(self.delete_button)

        layout.addWidget(self.empty_hint)
        layout.addLayout(own_buttons)

        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.view.currentItemChanged.connect(
            lambda current, previous: self.selection_changed.emit()
        )
        self.add_button.clicked.connect(self.add_requested.emit)
        self.delete_button.clicked.connect(self.delete_requested.emit)

    @property
    def group(self) -> str:
        """Ключ выбранной закладки."""

        return self.tabs.tabData(self.tabs.currentIndex())

    def selected_id(self) -> str | None:
        """Идентификатор модели, выбранной в списке."""

        item = self.view.currentItem()

        if item is None:
            return None

        return item.data(Qt.UserRole)

    def set_group(self, group: str) -> None:
        """Переключает закладку по ключу."""

        for index in range(self.tabs.count()):
            if self.tabs.tabData(index) == group:
                self.tabs.setCurrentIndex(index)

                return

    def refresh(
        self,
        models: list[dict],
        *,
        current: str,
        companions: set[str],
        conference: set[str],
        usable,
        keep_id: str | None = None,
    ) -> None:
        """Перерисовывает список текущей закладки."""

        self.view.blockSignals(True)
        self.view.clear()

        group = self.group
        is_conference = group == CONFERENCE_GROUP

        for index, model in enumerate(models):
            text = build_model_item_text(
                model,
                current,
                companions,
                usable=usable(model),
            )

            senator_slot = is_conference and (
                index < MAX_CONFERENCE_MODELS
            )

            if is_conference:
                text = f"{senator_title(index + 1)} · {text}"

            item = QListWidgetItem(text, self.view)
            item.setData(Qt.UserRole, model["id"])
            item.setData(SENATOR_ICON_ROLE, senator_slot)

            font = item.font()
            is_active = model["id"] == current
            font.setBold(is_active)
            item.setFont(font)

            if is_active:
                item.setForeground(QColor("#7cf58f"))
            elif not usable(model):
                item.setForeground(QColor("#6f7d72"))
            elif model["available"]:
                item.setForeground(QColor("#cfe8d2"))
            else:
                item.setForeground(QColor("#94a497"))

        target_id = keep_id or current
        row = 0

        for index in range(self.view.count()):
            if self.view.item(index).data(Qt.UserRole) == target_id:
                row = index

                break

        if self.view.count():
            self.view.setCurrentRow(row)
            self.view.doItemsLayout()

        self.view.blockSignals(False)

        is_own = group == "own"
        is_companions = group == COMPANION_GROUP

        if is_companions:
            self.empty_hint.setText(
                "Компаньонов пока нет.\n"
                "Отметь модель галочкой в её карточке."
            )
        elif is_conference:
            self.empty_hint.setText(
                "Участников сената пока нет.\n"
                "Отметь модель галочкой в её карточке."
            )
        else:
            self.empty_hint.setText("Своих моделей пока нет")

        self.empty_hint.setVisible(
            (is_own or is_companions or is_conference)
            and self.view.count() == 0
        )

    def select_id(self, model_id: str) -> None:
        """Выбирает строку по идентификатору модели."""

        for row in range(self.view.count()):
            if self.view.item(row).data(Qt.UserRole) == model_id:
                self.view.setCurrentRow(row)

                return

    def set_delete_enabled(self, enabled: bool) -> None:
        """Разрешает удаление только для своей модели."""

        self.delete_button.setEnabled(enabled)

    def relayout(self) -> None:
        """Пересчитывает строки после применения стилей окна."""

        self.view.doItemsLayout()
        self.view.viewport().update()

    def _on_tab_changed(self, index: int) -> None:
        """Показывает кнопки «Своих» и просит перерисовать список."""

        is_own = self.tabs.tabData(index) == "own"

        self.add_button.setVisible(is_own)
        self.delete_button.setVisible(is_own)

        self.group_changed.emit(index)
