# Giperion/terminal/ui/update_mixin.py                              v001
# Открытие окна «Обновление» из плиты «Система».
# Последнее изменение: первый вариант — проверка выпусков терминала.

from terminal.ui.dialogs_base import show_tool_window
from terminal.ui.update_dialog import UpdateDialog


class UpdateMixin:
    """Методы окна для обновления терминала-агента."""

    def open_update_dialog(self) -> None:
        """Открывает окно проверки и установки обновлений."""

        dialog = UpdateDialog(self.window)

        show_tool_window(self.window, dialog, "update")
