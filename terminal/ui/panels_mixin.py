# Giperion/terminal/ui/panels_mixin.py                              v021
# Панели окна: сборка из частей — ядро, модули, система, инструменты.
# Последнее изменение: методы разнесены по panels_core/side/misc.

from terminal.ui.panels_core import CorePanelMixin
from terminal.ui.panels_data import (
    EMPTY_MODULE_BUTTONS,
    MODULE_INFO,
    MODULE_ORDER,
    MODULE_SLOTS,
    VOICE_MAX_MS,
    VOICE_MIN_MS,
    VOICE_REMARKS,
)
from terminal.ui.panels_misc import PanelsMiscMixin
from terminal.ui.panels_side import SidePanelMixin

__all__ = [
    "EMPTY_MODULE_BUTTONS",
    "MODULE_INFO",
    "MODULE_ORDER",
    "MODULE_SLOTS",
    "PanelsMixin",
    "VOICE_MAX_MS",
    "VOICE_MIN_MS",
    "VOICE_REMARKS",
]


class PanelsMixin(
    CorePanelMixin,
    SidePanelMixin,
    PanelsMiscMixin,
):
    """Методы окна, отвечающие только за панели и модули."""
