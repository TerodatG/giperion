# Giperion/terminal/ui/rating_bars.py                                 v001
# Общие шкалы 0–5: сильные стороны, черты личности и характер дрона.
# Последнее изменение: вынесено из трёх окон.

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


def clear_layout(layout: QVBoxLayout) -> None:
    """Убирает старые строки, чтобы они не наложились на новые."""

    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()

        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


def fill_rating_bars(
    layout: QVBoxLayout,
    parent: QWidget,
    ratings: dict,
    *,
    name_width: int = 92,
    empty_text: str = "",
) -> None:
    """Рисует строки «название — шкала — оценка»."""

    clear_layout(layout)

    if not ratings:
        if empty_text:
            empty = QLabel(empty_text, parent)
            empty.setObjectName("strengthName")
            layout.addWidget(empty)

        return

    for title, value in ratings.items():
        row = QWidget(parent)

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)

        name = QLabel(str(title), row)
        name.setObjectName("strengthName")
        name.setFixedWidth(name_width)

        bar = QProgressBar(row)
        bar.setObjectName("strengthBar")
        bar.setRange(0, 5)
        bar.setValue(int(value))
        bar.setTextVisible(False)
        bar.setFixedHeight(10)

        score = QLabel(str(value), row)
        score.setObjectName("strengthValue")
        score.setFixedWidth(14)

        row_layout.addWidget(name)
        row_layout.addWidget(bar, 1)
        row_layout.addWidget(score)

        layout.addWidget(row)
