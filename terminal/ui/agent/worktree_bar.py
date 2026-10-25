# Giperion/terminal/ui/agent/worktree_bar.py                          v001
# Кнопки ветки задачи: слить в выбранную ветку или удалить.
# Последнее изменение: вынесено из agent_dialog.

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from config import BASE_DIR
from terminal.core.agent.worktrees import (
    current_branch,
    list_branches,
)


class WorktreeBar(QWidget):
    """Строка действий с отдельной веткой задачи."""

    merge_requested = Signal()
    remove_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.merge_button = QPushButton("Слить ветку", self)
        self.merge_button.setObjectName("workshopAction")
        self.merge_button.setVisible(False)
        self.merge_button.clicked.connect(self.merge_requested.emit)

        self.remove_button = QPushButton("Удалить ветку", self)
        self.remove_button.setObjectName("workshopAction")
        self.remove_button.setVisible(False)
        self.remove_button.clicked.connect(self.remove_requested.emit)

        self.target_combo = QComboBox(self)
        self.target_combo.setObjectName("targetBranch")
        self.target_combo.setVisible(False)
        self.target_combo.setToolTip(
            "В какую ветку слить результат задачи."
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.merge_button)
        layout.addWidget(self.target_combo)
        layout.addWidget(self.remove_button)
        layout.addStretch(1)

    def show_actions(self, visible: bool) -> None:
        """Показывает или скрывает действия ветки."""

        self.merge_button.setVisible(visible)
        self.remove_button.setVisible(visible)
        self.target_combo.setVisible(visible)

        if visible:
            self.refresh_branches()

    def refresh_branches(self) -> None:
        """Заполняет список веток и выбирает текущую."""

        self.target_combo.clear()
        self.target_combo.addItems(list_branches(BASE_DIR))

        current = current_branch(BASE_DIR)

        if current:
            self.target_combo.setCurrentText(current)

    @property
    def target_branch(self) -> str:
        """Выбранная ветка слияния."""

        return self.target_combo.currentText()
