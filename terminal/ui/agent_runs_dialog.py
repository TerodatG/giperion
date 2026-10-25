# Giperion/terminal/ui/agent_runs_dialog.py                          v001
# Окно «Журнал агента»: последние прогоны, шаги, время, итог.
# Последнее изменение: первый вариант — читает data/agent_runs.jsonl.

from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
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

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(refresh)
        row.addStretch(1)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(hint)
        self.body_layout.addWidget(self.view, 1)
        self.body_layout.addLayout(row)
        self.body_layout.addWidget(buttons)

        self._refresh()

    def _refresh(self) -> None:
        self.view.setPlainText(format_runs())


def show_agent_runs_dialog(parent) -> None:
    """Открывает немодальный журнал агента."""

    dialog = AgentRunsDialog(parent)
    show_tool_window(parent, dialog, "agent-runs")
