# Giperion/terminal/ui/settings_skins.py                             v002
# Раздел «Скины»: список, миниатюра окна и применение.
# Последнее изменение: кнопка «Применить» слева под состоянием.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from terminal.core.skins import SKINS, clean_skin_id, get_skin
from terminal.ui.skin_preview import SkinPreview


class SkinsPage(QWidget):
    """Страница выбора скина с предпросмотром миниатюры."""

    def __init__(
        self,
        parent,
        current_id: str,
        on_apply=None,
    ) -> None:
        super().__init__(parent)

        self.on_apply = on_apply
        self.current_id = clean_skin_id(current_id)
        self.selected_id = self.current_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("СКИНЫ", self)
        title.setObjectName("dialogTitle")

        hint = QLabel(
            "Внешний вид интерфейса: металл, экраны, подсветка и шрифты. "
            "Скин применяется сразу, без перезапуска.",
            self,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        body = QHBoxLayout()
        body.setSpacing(12)

        self.skin_list = QListWidget(self)
        self.skin_list.setObjectName("skinList")
        self.skin_list.setFixedWidth(226)
        self.skin_list.setSelectionMode(QListWidget.SingleSelection)

        for skin in SKINS:
            item = QListWidgetItem("", self.skin_list)
            item.setData(Qt.UserRole, skin.id)

        self.preview = SkinPreview(self)

        preview_frame = QWidget(self)
        preview_frame.setObjectName("skinPreviewFrame")

        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setContentsMargins(6, 6, 6, 6)
        preview_layout.addWidget(self.preview)

        self.description = QLabel("", self)
        self.description.setObjectName("dialogHint")
        self.description.setWordWrap(True)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("settingsStatus")
        self.status_label.setWordWrap(True)

        self.apply_button = QPushButton("Применить", self)
        self.apply_button.setCursor(Qt.ArrowCursor)
        self.apply_button.setMinimumWidth(140)
        self.apply_button.clicked.connect(self._apply)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(preview_frame, 1)
        right.addWidget(self.description)
        right.addWidget(self.status_label)
        right.addWidget(self.apply_button, 0, Qt.AlignLeft)

        body.addWidget(self.skin_list)
        body.addLayout(right, 1)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(body, 1)

        self._refresh_labels()

        self.skin_list.currentItemChanged.connect(
            lambda current, previous: self._on_row_changed(current)
        )

        for row in range(self.skin_list.count()):
            if self.skin_list.item(row).data(Qt.UserRole) == self.current_id:
                self.skin_list.setCurrentRow(row)

                break

    # --- Служебное ---

    def _refresh_labels(self) -> None:
        """Пишет в списке состояние каждого скина."""

        for row in range(self.skin_list.count()):
            item = self.skin_list.item(row)
            skin = get_skin(str(item.data(Qt.UserRole)))

            mark = "активен" if skin.id == self.current_id else skin.status_text
            item.setText(f"{skin.name}\n{skin.tagline}\n{mark}")

    def _on_row_changed(self, current: QListWidgetItem | None) -> None:
        """Показывает выбранный скин в предпросмотре."""

        if current is None:
            return

        self._select(str(current.data(Qt.UserRole)))

    def _select(self, skin_id: str) -> None:
        """Обновляет предпросмотр, описание и кнопку."""

        skin = get_skin(skin_id)

        self.selected_id = skin.id
        self.preview.set_skin(skin)
        self.description.setText(skin.description)

        if skin.id == self.current_id:
            self.status_label.setText("Этот скин уже активен.")
            self.apply_button.setEnabled(False)
        elif not skin.ready:
            self.status_label.setText(
                "Готовится: доступен только предпросмотр."
            )
            self.apply_button.setEnabled(False)
        else:
            self.status_label.setText(
                f"Нажми «Применить», чтобы включить «{skin.name}»."
            )
            self.apply_button.setEnabled(True)

    def _apply(self) -> None:
        """Применяет выбранный скин через главное окно."""

        skin = get_skin(self.selected_id)

        if not skin.ready:
            return

        applied = skin.id

        if self.on_apply is not None:
            applied = clean_skin_id(self.on_apply(skin.id) or skin.id)

        self.current_id = applied
        self._refresh_labels()
        self._select(skin.id)

        if applied == skin.id:
            self.status_label.setText(
                f"Скин «{skin.name}» применён."
            )
