# Giperion/terminal/ui/performance_mixin.py                         v001
# Открытие окна «Производительность» из плиты «Система».
# Последнее изменение: первый вариант — кнопка живых графиков.

from terminal.ui.dialogs_base import show_tool_window
from terminal.ui.performance_dialog import PerformanceDialog


class PerformanceMixin:
    """Методы окна для живых показателей компьютера."""

    def open_performance_dialog(self) -> None:
        """Открывает окно с графиками нагрузки на компьютер."""

        dialog = PerformanceDialog(self.window)

        show_tool_window(self.window, dialog, "performance")
