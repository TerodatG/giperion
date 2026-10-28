# Giperion/terminal/ui/update_mixin.py                              v002
# Открытие окна «Обновление» и тихая проверка при запуске.

import os
import threading

from PySide6.QtCore import QTimer

from terminal.core.app_version import skipped_version
from terminal.core.update_service import check_updates
from terminal.ui.dialogs_base import show_tool_window
from terminal.ui.update_dialog import UpdateDialog

# Проверка стартует не сразу: окно должно успеть отрисоваться.
STARTUP_DELAY_MS = 5000

# Как часто окно смотрит, закончилась ли фоновая проверка.
POLL_MS = 300

# Отключает проверку при запуске (нужно тестам и офлайн-сборкам).
DISABLE_ENV = "GIPERION_NO_UPDATE_CHECK"


class UpdateMixin:
    """Методы окна для обновления терминала-агента."""

    def open_update_dialog(self) -> None:
        """Открывает окно проверки и установки обновлений."""

        dialog = UpdateDialog(self.window)

        show_tool_window(self.window, dialog, "update")

    def schedule_update_check(self) -> None:
        """Тихо проверяет обновления через несколько секунд после старта."""

        if os.environ.get(DISABLE_ENV):
            return

        self._update_state = {"done": False, "result": None}
        self._update_poll = QTimer(self.window)
        self._update_poll.setInterval(POLL_MS)
        self._update_poll.timeout.connect(self._poll_update_check)

        QTimer.singleShot(STARTUP_DELAY_MS, self._start_update_check)

    def _start_update_check(self) -> None:
        """Запускает проверку в фоне, чтобы окно не замирало."""

        state = getattr(self, "_update_state", None)

        if state is None or state["done"]:
            return

        thread = threading.Thread(
            target=self._run_update_check,
            args=(state,),
            daemon=True,
        )
        thread.start()

        self._update_poll.start()

    @staticmethod
    def _run_update_check(state: dict) -> None:
        """Выполняет проверку и складывает итог в состояние."""

        try:
            state["result"] = check_updates()
        except Exception:  # noqa: BLE001 — молчаливая фоновая проверка
            state["result"] = None
        finally:
            state["done"] = True

    def _poll_update_check(self) -> None:
        """Забирает итог фоновой проверки и пишет подсказку в журнал."""

        state = getattr(self, "_update_state", None)

        if state is None or not state["done"]:
            return

        self._update_poll.stop()

        result = state["result"]

        if result is None or result.error or not result.new_releases:
            return

        latest = result.available

        if latest is None or latest.version == skipped_version():
            return

        self.append_system(
            f"Доступно обновление {latest.version}. "
            "Открой «Система» → «Обновление»."
        )
