# Giperion/terminal/ui/keybindings_mixin.py                          v001
# Горячие клавиши окна: установка, снятие и проверка нажатий.
# Последнее изменение: первый вариант — QShortcut по назначениям.

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from terminal.core.keybindings import (
    ACTIONS,
    load_bindings,
    normalize_binding,
)


class KeybindingsMixin:
    """Методы окна для назначенных клавиш."""

    def install_shortcuts(self, bindings: dict | None = None) -> None:
        """Ставит горячие клавиши по назначениям.

        Старые ярлыки снимаются, чтобы после смены не осталось двух
        обработчиков на одно действие.
        """

        self.keybindings = dict(bindings or load_bindings())

        for shortcut in getattr(self, "shortcuts", []):
            shortcut.setEnabled(False)
            shortcut.deleteLater()

        self.shortcuts = []
        handlers = self._shortcut_handlers()

        for action in ACTIONS:
            if action.scope != "window":
                continue

            sequence = QKeySequence(
                self.keybindings.get(action.id, "")
            )

            if sequence.isEmpty():
                continue

            handler = handlers.get(action.id)

            if handler is None:
                continue

            shortcut = QShortcut(sequence, self.window)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(handler)

            self.shortcuts.append(shortcut)

    def _shortcut_handlers(self) -> dict:
        """Действия окна, доступные по горячим клавишам."""

        return {
            "new_chat": self._new_chat_clicked,
            "focus_input": lambda: self.input.setFocus(),
            "clear_chat": self.clear_chat,
            "settings": self.open_settings_dialog,
            "models": self.open_models_dialog,
            "drones": self.open_pets_dialog,
            "agent": self.open_agent_dialog,
            "performance": self.open_performance_dialog,
            "update": self.open_update_dialog,
        }

    def binding_matches(self, action_id: str, event) -> bool:
        """Совпадает ли нажатие с назначением действия.

        Enter на цифровом блоке и Return считаются одной клавишей.
        """

        binding = getattr(self, "keybindings", {}).get(action_id, "")

        if not binding:
            return False

        pressed = QKeySequence(
            event.keyCombination()
        ).toString(QKeySequence.PortableText)

        def unified(value: str) -> str:
            return normalize_binding(value).replace("enter", "return")

        return unified(pressed) == unified(binding)
