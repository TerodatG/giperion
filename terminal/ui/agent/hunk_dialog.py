# Giperion/terminal/ui/agent/hunk_dialog.py                            v001
# Выбор отдельных участков диффа для частичного применения.
# Последнее изменение: первый вариант — чекбоксы и применение.

from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from terminal.core.agent.diff_marks import hunks
from terminal.ui.dialogs_base import SkinDialog


class HunkDialog(SkinDialog):
    """Список изменённых участков с галочками."""

    def __init__(self, parent, old_text: str, new_text: str) -> None:
        super().__init__(
            parent,
            "Участки диффа",
            min_width=640,
            min_height=420,
        )

        layout = QVBoxLayout(self)
        hint = QLabel(
            "Сними галочку, чтобы не применять этот участок. "
            "Номера строк — по исходному файлу.",
            self,
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.boxes: list[tuple[int, QCheckBox]] = []

        for hunk in hunks(old_text, new_text):
            label = (
                f"Строка {hunk.old_start}: "
                f"−{len(hunk.old_lines)} / +{len(hunk.new_lines)}"
            )
            box = QCheckBox(label, self)
            box.setChecked(True)
            box.setToolTip(
                "\n".join(
                    ["− " + line for line in hunk.old_lines]
                    + ["+ " + line for line in hunk.new_lines]
                )[:2_000]
            )
            layout.addWidget(box)
            self.boxes.append((hunk.index, box))

        if not self.boxes:
            layout.addWidget(QLabel("Изменений нет.", self))

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            self,
        )
        buttons.button(QDialogButtonBox.Ok).setText("Применить")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self) -> set[int]:
        """Индексы отмеченных участков."""

        return {
            index for index, box in self.boxes if box.isChecked()
        }


def show_hunk_dialog(
    parent,
    old_text: str,
    new_text: str,
) -> set[int] | None:
    """Открывает выбор участков; None — пользователь отменил."""

    dialog = HunkDialog(parent, old_text, new_text)

    if dialog.exec() != dialog.DialogCode.Accepted:
        return None

    return dialog.selected()
