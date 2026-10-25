# Giperion/terminal/ui/transcript_mixin.py                              v005
# Терминал связи: сборка ленты и печати из двух миксинов.
# Последнее изменение: методы разнесены по render/messages.

from terminal.ui.transcript_messages import TranscriptMessagesMixin
from terminal.ui.transcript_render import TranscriptRenderMixin

__all__ = ["TranscriptMixin"]


class TranscriptMixin(
    TranscriptRenderMixin,
    TranscriptMessagesMixin,
):
    """Методы окна, отвечающие только за историю чата и её отрисовку."""
