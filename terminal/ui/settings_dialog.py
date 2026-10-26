# Giperion/app/ui/settings_dialog.py                                v007
# Вложенное окно настроек: «Вид», «Скины», «Клавиши» и «О нас».
# Последнее изменение: раздел «Справка» вынесен в отдельное окно.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from terminal.ui.dialogs_base import SkinDialog
from terminal.ui.settings_about import build_about_page
from terminal.ui.settings_keys import KeysPage
from terminal.ui.settings_skins import SkinsPage
from terminal.ui.view_settings import ViewSettingsPanel


class SettingsDialog(SkinDialog):
    """Вложенное окно настроек с разделами «Вид», «Скины», «Клавиши», «О нас»."""

    def __init__(
        self,
        parent,
        chat_font_family: str,
        chat_font_size: int,
        colors: dict[str, str],
        styles: dict[str, str],
        response_settings: dict,
        on_apply,
        font_sizes: dict[str, int] | None = None,
        on_apply_skin=None,
        skin_id: str = "terminal",
        on_apply_keys=None,
        keybindings: dict | None = None,
    ) -> None:
        super().__init__(
            parent,
            "Настройки",
            min_width=1000,
            min_height=716,
        )

        self.on_apply = on_apply

        container = QHBoxLayout()
        container.setContentsMargins(0, 0, 0, 0)
        container.setSpacing(12)

        nav = QWidget(self.body)
        nav.setObjectName("settingsNav")
        nav.setAttribute(Qt.WA_StyledBackground, True)
        nav.setFixedWidth(176)

        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(10, 8, 10, 8)
        nav_layout.setSpacing(6)

        nav_caption = QLabel("РАЗДЕЛЫ", nav)
        nav_caption.setObjectName("settingsSection")

        nav_layout.addWidget(nav_caption)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self.nav_buttons = []

        for index, title in enumerate(
            ("ВИД", "СКИНЫ", "КЛАВИШИ", "О НАС")
        ):
            button = QPushButton(title, nav)
            button.setObjectName("settingsNavButton")
            button.setCheckable(True)
            button.setCursor(Qt.ArrowCursor)
            button.setMinimumHeight(36)
            button.setFocusPolicy(Qt.NoFocus)

            self.nav_group.addButton(button, index)
            self.nav_buttons.append(button)
            nav_layout.addWidget(button)

        nav_layout.addStretch(1)

        self.view_panel = ViewSettingsPanel(
            self,
            chat_font_family,
            chat_font_size,
            colors,
            styles,
            response_settings,
            font_sizes,
        )

        self.stack = QStackedWidget(self.body)
        self.stack.addWidget(self.view_panel)

        self.skins_panel = SkinsPage(
            self,
            skin_id,
            on_apply=on_apply_skin,
        )

        self.stack.addWidget(self.skins_panel)

        self.keys_panel = KeysPage(
            self,
            bindings=keybindings,
            on_apply=on_apply_keys,
        )

        self.stack.addWidget(self.keys_panel)
        self.stack.addWidget(self._build_about_page())

        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        self.nav_buttons[0].setChecked(True)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)
        content.addWidget(self.stack, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self.status_label = QLabel(
            "Изменения вступают в силу после «Применить».",
            self.body,
        )
        self.status_label.setObjectName("settingsStatus")

        self.apply_button = QPushButton("Применить", self.body)
        self.apply_button.setCursor(Qt.ArrowCursor)
        self.apply_button.clicked.connect(self._apply)

        close_button = QPushButton("Закрыть", self.body)
        close_button.setCursor(Qt.ArrowCursor)
        close_button.clicked.connect(self.accept)

        bottom.addWidget(self.status_label)
        bottom.addStretch(1)
        bottom.addWidget(self.apply_button)
        bottom.addWidget(close_button)

        content.addLayout(bottom)

        container.addWidget(nav)
        container.addLayout(content, 1)

        self.body_layout.addLayout(container, 1)

        self.stack.currentChanged.connect(self._section_changed)
        self._section_changed(self.stack.currentIndex())

    def _section_changed(self, index: int) -> None:
        """Показывает «Применить» только в разделе «Вид»."""

        is_view = index == 0

        self.apply_button.setVisible(is_view)
        self.status_label.setVisible(is_view)

    def _build_about_page(self) -> QWidget:
        """Собирает страницу «О нас»."""

        return build_about_page(self)

    def _apply(self) -> None:
        """Передаёт настройки главному окну."""

        self.on_apply(*self.view_panel.settings_payload())
        self.status_label.setText("Настройки применены.")
