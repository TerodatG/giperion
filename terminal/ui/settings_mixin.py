# Giperion/app/ui/settings_mixin.py                                 v005
# Применение настроек вида, шрифта, скина и клавиш.
# Последнее изменение: применение назначенных клавиш.

from terminal.core.keybindings import load_bindings, save_bindings
from terminal.core.skins import get_skin, save_skin_id
from terminal.core.window_settings import (
    DEFAULT_FONT_SIZES,
    DEFAULT_RESPONSE_SETTINGS,
    DEFAULT_STYLES,
)
from terminal.ui.dialogs_base import show_tool_window
from terminal.ui.settings_dialog import SettingsDialog
from terminal.ui.theme import DEFAULT_COLORS
from terminal.ui.window_style import build_window_style


class SettingsMixin:
    """Методы окна для открытия и применения настроек."""

    def _apply_chat_font(self) -> None:
        """Применяет гарнитуру и размер шрифта к истории чата."""

        font = self.chat.font()

        if self.chat_font_family:
            font.setFamily(self.chat_font_family)

        font.setPointSize(self.chat_font_size)

        self.chat.setFont(font)

    def open_settings_dialog(self) -> None:
        """Открывает вложенное окно настроек."""

        dialog = SettingsDialog(
            self.window,
            self.chat_font_family,
            self.chat_font_size,
            self.colors,
            self.styles,
            self.response_settings,
            on_apply=self.apply_view_settings,
            font_sizes=self.font_sizes,
            on_apply_skin=self.apply_skin,
            skin_id=getattr(self, "skin_id", "terminal"),
            on_apply_keys=self.apply_keybindings,
            keybindings=dict(
                getattr(self, "keybindings", None) or load_bindings()
            ),
        )

        show_tool_window(self.window, dialog, "settings")

    def apply_skin(self, skin_id: str) -> str:
        """Применяет скин интерфейса и запоминает выбор."""

        skin = get_skin(skin_id)

        if not skin.ready:
            return getattr(self, "skin_id", "terminal")

        self.skin_id = save_skin_id(skin.id)
        self.window.setStyleSheet(build_window_style(self.skin_id))

        return self.skin_id

    def apply_keybindings(self, bindings: dict) -> dict:
        """Сохраняет назначения клавиш и ставит горячие клавиши."""

        saved = save_bindings(bindings)
        self.install_shortcuts(saved)

        return saved

    def apply_view_settings(
        self,
        chat_font_family: str,
        chat_font_size: int,
        colors: dict[str, str],
        styles: dict[str, str],
        response_settings: dict | None = None,
        font_sizes: dict[str, int] | None = None,
    ) -> None:
        """Применяет настройки вида и перерисовывает чат."""

        self.chat_font_family = chat_font_family
        self.chat_font_size = chat_font_size
        self.colors = {
            **DEFAULT_COLORS,
            **dict(colors),
        }
        self.styles = {
            **DEFAULT_STYLES,
            **dict(styles),
        }
        self.font_sizes = {
            **DEFAULT_FONT_SIZES,
            **dict(font_sizes or {}),
        }

        if response_settings is not None:
            self.response_settings = {
                **DEFAULT_RESPONSE_SETTINGS,
                **dict(response_settings),
            }

        self._save_window_settings()

        self._apply_chat_font()
        self._rebuild_chat()
