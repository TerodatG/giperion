# Giperion/terminal/ui/pets_dialog.py                                  v008
# Совместимый вход в окно «Дроны»; код живёт в пакете terminal/ui/pets.
# Последнее изменение: show_pets_dialog переехал в terminal/ui/pets.

from terminal.ui.pets import show_pets_dialog
from terminal.ui.pets.dialogs import (
    ask_new_pet as _ask_new_pet,
)
from terminal.ui.pets.dialogs import (
    ask_nickname as _ask_nickname,
)

__all__ = [
    "_ask_new_pet",
    "_ask_nickname",
    "show_pets_dialog",
]
