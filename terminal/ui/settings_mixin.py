# Giperion/app/ui/settings_mixin.py                                 v003
# Применение настроек вида, шрифта и заголовка окна.
# Последнее изменение: без подписи на планке заголовка.

from terminal.core.window_settings import (
    DEFAULT_FONT_SIZES,
    DEFAULT_RESPONSE_SETTINGS,
    DEFAULT_STYLES,
)
from terminal.ui.dialogs_base import show_tool_window
from terminal.ui.settings_dialog import SettingsDialog
from terminal.ui.theme import DEFAULT_COLORS


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
        )

        show_tool_window(self.window, dialog, "settings")

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
