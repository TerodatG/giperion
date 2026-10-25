# Giperion/terminal/ui/widgets/decorations.py                                  v001
# Размерный уголок.
# Последнее изменение: вынесено из widgets.py.


from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QSizeGrip,
)


class FuturisticGrip(QSizeGrip):
    """Размерный уголок в стиле окна: три диагональные риски."""

    def paintEvent(self, event) -> None:
        """Рисует свой узор вместо системного."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        pen = QPen(QColor(190, 150, 110, 190))
        pen.setWidthF(1.4)

        painter.setPen(pen)

        width = self.width()
        height = self.height()

        for offset in (4, 8, 12):
            painter.drawLine(
                width - offset - 2,
                height - 2,
                2,
                height - offset - 2,
            )

