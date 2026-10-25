# Giperion/terminal/ui/agent_runs_dialog.py                          v001
# Окно «Журнал агента»: последние прогоны, шаги, время, итог.

from pathlib import (
    Path,  # Последнее изменение: первый вариант — читает data/agent_runs.jsonl.
)

from PySide6.QtWidgets import (
    QComboBox,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
)

from config import BASE_DIR
from terminal.core.agent.rollback import (
    can_rollback,
    plan_rollback,
    rollback_run,
)
from terminal.core.agent.runs import read_runs
from terminal.ui.dialogs_base import SkinDialog, show_tool_window


def format_runs(limit: int = 30) -> str:
    """Собирает журнал в текст для окна."""

    records = read_runs(limit)

    if not records:
        return "Журнал пуст: агент ещё не запускал задачи."

    lines = []

    for record in reversed(records):
        task = str(record.get("task", "")).splitlines()

        title = task[0][:80] if task else "без описания"
        status = (
            "отменено"
            if record.get("cancelled")
            else ("ошибка" if record.get("error") else "готово")
        )

        lines.append(
            f"{record.get('created_at', '—')} · "
            f"{record.get('model', '—')} · {status}"
        )
        lines.append(
            f"  {title}"
        )
        lines.append(
            "  шагов: "
            f"{record.get('steps', 0)} · "
            "подтверждений: "
            f"{record.get('approvals', 0)} · "
            f"{record.get('duration_s', 0)} с"
            + (
                f" · {int(record.get('tokens') or 0) // 1000}k токенов"
                if record.get("tokens")
                else ""
            )
            + (
                f" · ${float(record.get('cost') or 0):.4f}"
                if record.get("cost")
                else ""
            )
            + (
                f" · повторов: {int(record.get('retries') or 0)}"
                if record.get("retries")
                else ""
            )
        )

        error = str(record.get("error", "")).strip()

        if error:
            lines.append("  ошибка: " + error[:200])

        lines.append("")

    return "\n".join(lines).strip()


class AgentRunsDialog(SkinDialog):
    """Показывает последние прогоны агента."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Журнал агента",
            min_width=820,
            min_height=560,
        )

        title = QLabel("ЖУРНАЛ АГЕНТА", self)
        title.setObjectName("dialogTitle")

        hint = QLabel(
            "Последние задачи: модель, шаги, подтверждения, время и итог. "
            "Файл: data/agent_runs.jsonl.",
            self,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        self.view = QPlainTextEdit(self)
        self.view.setObjectName("agentTrace")
        self.view.setReadOnly(True)

        refresh = QPushButton("Обновить", self)
        refresh.setObjectName("workshopAction")
        refresh.clicked.connect(self._refresh)

        self.run_combo = QComboBox(self)
        self.run_combo.setObjectName("approvalPolicy")
        self.run_combo.setMinimumWidth(420)
        self.run_combo.currentIndexChanged.connect(self._update_hint)

        self.rollback_button = QPushButton("Откатить файлы…", self)
        self.rollback_button.setObjectName("workshopAction")
        self.rollback_button.setEnabled(False)
        self.rollback_button.clicked.connect(self._rollback)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("dialogHint")
        self.status_label.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)

        choose_row = QHBoxLayout()
        choose_row.setSpacing(8)
        choose_row.addWidget(QLabel("Прогон:", self))
        choose_row.addWidget(self.run_combo, 1)
        choose_row.addWidget(self.rollback_button)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(refresh)
        row.addStretch(1)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(hint)
        self.body_layout.addWidget(self.view, 1)
        self.body_layout.addLayout(choose_row)
        self.body_layout.addWidget(self.status_label)
        self.body_layout.addLayout(row)
        self.body_layout.addWidget(buttons)

        self._refresh()

    def _refresh(self) -> None:
        self._records = [
            record
            for record in reversed(read_runs(60))
            if can_rollback(record)
        ]

        self.run_combo.blockSignals(True)
        self.run_combo.clear()

        for record in self._records:
            task = str(record.get("task") or "").splitlines()
            title = task[0][:48] if task else "без описания"
            files = record.get("files") or []

            self.run_combo.addItem(
                f"{record.get('created_at', '—')} · {title} · "
                f"файлов: {len(files)}"
            )

        self.run_combo.blockSignals(False)
        self.view.setPlainText(format_runs())
        self._update_hint()

    def _update_hint(self) -> None:
        """Показывает, какие файлы будут возвращены."""

        record = self._current_record()

        if record is None:
            self.status_label.setText(
                "В журнале нет прогонов, которые меняли файлы."
            )
            self.rollback_button.setEnabled(False)

            return

        root = Path(str(record.get("root") or BASE_DIR))
        plan = plan_rollback(root, record)
        ready = [item for item in plan if item["backup"] is not None]
        missing = [item for item in plan if item["backup"] is None]

        text = (
            f"Будет восстановлено файлов: {len(ready)} из {len(plan)}."
        )

        if missing:
            text += " Без копии: " + ", ".join(
                item["path"] for item in missing[:4]
            )

        self.status_label.setText(text)
        self.rollback_button.setEnabled(bool(ready))

    def _current_record(self) -> dict | None:
        index = self.run_combo.currentIndex()

        if index < 0 or index >= len(self._records):
            return None

        return self._records[index]

    def _rollback(self) -> None:
        """Возвращает файлы выбранного прогона из резервных копий."""

        record = self._current_record()

        if record is None:
            return

        root = Path(str(record.get("root") or BASE_DIR))
        plan = plan_rollback(root, record)
        ready = [item["path"] for item in plan if item["backup"] is not None]

        if not ready:
            self.status_label.setText("Нет сохранённых копий для отката.")
            return

        answer = QMessageBox.question(
            self,
            "Откатить файлы",
            "Вернуть к состоянию до прогона:\n\n"
            + "\n".join(ready[:10])
            + (
                f"\n… и ещё {len(ready) - 10}"
                if len(ready) > 10
                else ""
            )
            + "\n\nТекущие изменения этих файлов будут потеряны.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        lines = rollback_run(root, record)

        self.status_label.setText(" · ".join(lines[:6]))
        self._refresh()


def show_agent_runs_dialog(parent) -> None:
    """Открывает немодальный журнал агента."""

    dialog = AgentRunsDialog(parent)
    show_tool_window(parent, dialog, "agent-runs")
