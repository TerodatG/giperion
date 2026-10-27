# Giperion/terminal/ui/agent/approval.py                              v001
# Панель подтверждения: дифф, правка текста и «не спрашивать».
# Последнее изменение: вынесено из agent_dialog.

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from terminal.core.agent.diff_marks import (
    LineSpan,
    apply_hunks,
)
from terminal.core.agent.diff_marks import (
    diff_marks as build_marks,
)
from terminal.ui.agent.constants import REMEMBER_TITLES
from terminal.ui.agent.hunk_dialog import show_hunk_dialog


class ApprovalPanel(QFrame):
    """Подтверждение действия агента с редактором итогового текста."""

    resolved = Signal(bool, object, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setObjectName("paramsPlate")
        self.setVisible(False)

        self.request = None
        self._editing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        self.title = QLabel("ПОДТВЕРЖДЕНИЕ", self)
        self.title.setObjectName("paramsPlateTitle")

        self.detail = QPlainTextEdit(self)
        self.detail.setObjectName("agentTrace")
        self.detail.setReadOnly(True)
        self.detail.setFixedHeight(200)

        self.edit_split = QWidget(self)
        self.edit_split.setVisible(False)

        split_layout = QHBoxLayout(self.edit_split)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(6)

        old_column = QVBoxLayout()
        old_column.setSpacing(2)
        old_caption = QLabel("БЫЛО", self.edit_split)
        old_caption.setObjectName("paramsPlateTitle")
        self.old_view = QPlainTextEdit(self.edit_split)
        self.old_view.setObjectName("agentTrace")
        self.old_view.setReadOnly(True)
        self.old_view.setFixedHeight(200)
        old_column.addWidget(old_caption)
        old_column.addWidget(self.old_view)

        new_column = QVBoxLayout()
        new_column.setSpacing(2)
        new_caption = QLabel("СТАНЕТ", self.edit_split)
        new_caption.setObjectName("paramsPlateTitle")
        self.edit_area = QPlainTextEdit(self.edit_split)
        self.edit_area.setObjectName("agentTask")
        self.edit_area.setFixedHeight(200)
        self.edit_area.textChanged.connect(self._schedule_highlights)
        new_column.addWidget(new_caption)
        new_column.addWidget(self.edit_area)

        split_layout.addLayout(old_column, 1)
        split_layout.addLayout(new_column, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        self.allow_checkbox = QCheckBox(
            "Не спрашивать это до конца задачи",
            self,
        )
        self.allow_checkbox.setObjectName("approvalPolicy")
        self.allow_checkbox.setVisible(False)

        self.batch_checkbox = QCheckBox(
            "Не спрашивать все правки до конца задачи",
            self,
        )
        self.batch_checkbox.setObjectName("approvalPolicy")
        self.batch_checkbox.setVisible(False)
        self.batch_checkbox.setToolTip(
            "Автоматически разрешать последующие записи файлов, "
            "кроме git-коммитов."
        )

        self.approve_button = QPushButton("Одобрить", self)
        self.approve_button.setObjectName("workshopAction")
        self.approve_button.clicked.connect(self.approve)

        self.edit_button = QPushButton("Править", self)
        self.edit_button.setObjectName("workshopAction")
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self._toggle_edit)

        self.hunks_button = QPushButton("Участки…", self)
        self.hunks_button.setObjectName("workshopAction")
        self.hunks_button.setVisible(False)
        self.hunks_button.setToolTip(
            "Применить только выбранные участки диффа."
        )
        self.hunks_button.clicked.connect(self._pick_hunks)

        self.reject_button = QPushButton("Отклонить", self)
        self.reject_button.setObjectName("workshopAction")
        self.reject_button.clicked.connect(self.reject)

        buttons.addWidget(self.approve_button)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.hunks_button)
        buttons.addWidget(self.reject_button)
        buttons.addStretch(1)

        layout.addWidget(self.title)
        layout.addWidget(self.detail)
        layout.addWidget(self.edit_split)
        layout.addWidget(self.allow_checkbox)
        layout.addWidget(self.batch_checkbox)
        layout.addLayout(buttons)

        self._highlight_timer = QTimer(self)
        self._highlight_timer.setSingleShot(True)
        self._highlight_timer.setInterval(180)
        self._highlight_timer.timeout.connect(self._refresh_highlights)

    def show_request(self, request) -> None:
        """Показывает новое подтверждение."""

        self.request = request
        self.title.setText(request.title.upper())
        detail = request.detail

        if getattr(request, "audit_hash", ""):
            detail += "\n\nаудит: " + str(request.audit_hash)[:16]

        self.detail.setPlainText(detail)
        self.old_view.setPlainText(request.old_text or "")
        self.edit_area.setPlainText(request.new_text or "")

        self.reset()
        self.edit_button.setEnabled(request.new_text is not None)
        self.hunks_button.setVisible(
            request.new_text is not None
            and request.old_text is not None
        )

        remember_title = REMEMBER_TITLES.get(request.kind, "")

        self.allow_checkbox.setText(remember_title)
        self.allow_checkbox.setChecked(False)
        self.allow_checkbox.setVisible(
            bool(remember_title and request.key)
        )
        self.batch_checkbox.setChecked(False)
        self.batch_checkbox.setVisible(request.new_text is not None)

        self._refresh_highlights()
        self.setVisible(True)

    def hide_panel(self) -> None:
        """Скрывает панель и сбрасывает режим правки."""

        self.setVisible(False)
        self.reset()

    def reset(self) -> None:
        """Возвращает панель к просмотру диффа."""

        self._editing = False
        self.hunks_button.setVisible(False)
        self.batch_checkbox.setVisible(False)
        self.edit_button.setText("Править")
        self.edit_split.setVisible(False)
        self.detail.setVisible(True)
        self.old_view.setExtraSelections([])
        self.edit_area.setExtraSelections([])

    def approve(self) -> None:
        """Сообщает об одобрении и передаёт правку, если она есть."""

        text = None

        if (
            self._editing
            and self.request is not None
            and self.request.new_text is not None
        ):
            text = self.edit_area.toPlainText()

        remember = bool(
            self.request is not None
            and self.request.key
            and self.allow_checkbox.isChecked()
        )

        self.resolved.emit(True, text, remember)

    def reject(self) -> None:
        """Сообщает об отклонении действия."""

        self.resolved.emit(False, None, False)

    def batch_requested(self) -> bool:
        """Просил ли пользователь не спрашивать все правки."""

        return bool(self.batch_checkbox.isChecked())

    def _toggle_edit(self) -> None:
        """Переключает дифф и редактируемый текст."""

        if self.request is None:
            return

        self._editing = not self._editing
        self.detail.setVisible(not self._editing)
        self.edit_split.setVisible(self._editing)
        self.edit_button.setText(
            "К диффу" if self._editing else "Править"
        )

    def _pick_hunks(self) -> None:
        """Применяет только выбранные участки диффа."""

        if (
            self.request is None
            or self.request.old_text is None
            or self.request.new_text is None
        ):
            return

        selected = show_hunk_dialog(
            self,
            self.request.old_text,
            self.request.new_text,
        )

        if selected is None:
            return

        text = apply_hunks(
            self.request.old_text,
            self.request.new_text,
            selected,
        )

        if not self._editing:
            self._toggle_edit()

        self.edit_area.setPlainText(text)
        self._refresh_highlights()

    def _schedule_highlights(self) -> None:
        """Пересчитывает подсветку после правки текста."""

        self._highlight_timer.start()

    def _refresh_highlights(self) -> None:
        """Подсвечивает изменённые строки и слова с обеих сторон."""

        if self.request is None:
            return

        marks = build_marks(
            self.old_view.toPlainText(),
            self.edit_area.toPlainText(),
        )

        self.old_view.setExtraSelections(
            self._selections(
                self.old_view,
                marks.old_lines,
                marks.old_spans,
                "#4a1f1a",
            )
        )
        self.edit_area.setExtraSelections(
            self._selections(
                self.edit_area,
                marks.new_lines,
                marks.new_spans,
                "#123d1f",
            )
        )

    def _selections(
        self,
        view: QPlainTextEdit,
        lines: frozenset[int],
        spans: tuple[LineSpan, ...],
        color: str,
    ) -> list:
        """Собирает подсветку строк и слов одного редактора."""

        selections = []
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(color))

        for index in sorted(lines):
            block = view.document().findBlockByNumber(index)

            if not block.isValid():
                continue

            cursor = QTextCursor(block)
            cursor.select(QTextCursor.LineUnderCursor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = fmt

            selections.append(selection)

        for span in spans:
            block = view.document().findBlockByNumber(span.line)

            if not block.isValid():
                continue

            cursor = QTextCursor(block)
            start = block.position() + span.start
            end = block.position() + span.end

            if end <= start:
                continue

            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format = fmt

            selections.append(selection)

        return selections
