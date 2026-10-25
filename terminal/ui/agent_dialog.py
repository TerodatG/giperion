# Giperion/terminal/ui/agent_dialog.py                               v001
# Окно «Агент»: задача, лента шагов и остановка. Только чтение.
# Последнее изменение: первый вариант — read-only цикл с трейсом.

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import BASE_DIR
from terminal.core.agent.brain import ModelBrain
from terminal.core.helper_model import get_helper_model
from terminal.core.model_registry import (
    DEFAULT_MODEL_ID,
    get_active_model,
)
from terminal.ui.agent_job import AgentJob
from terminal.ui.dialogs_base import SkinDialog, show_tool_window

MAX_STEPS = 8
POLL_MS = 120

STEP_MARKS = {
    "tool": "→",
    "answer": "✓",
    "error": "!",
}


def _pick_model() -> dict | None:
    """Берёт активную внешнюю модель или лучшего помощника."""

    active = get_active_model()

    if (
        active is not None
        and active["id"] != DEFAULT_MODEL_ID
        and active.get("model_id")
    ):
        return active

    return get_helper_model()


class AgentDialog(SkinDialog):
    """Окно агента; при закрытии останавливает текущую задачу."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Агент",
            min_width=900,
            min_height=640,
        )

        self.job: AgentJob | None = None
        self._shown = 0

        self._build()
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

    def _build(self) -> None:
        """Собирает поля, кнопки и ленту шагов."""

        title = QLabel("АГЕНТ", self)
        title.setObjectName("dialogTitle")

        subtitle = QLabel(
            "Задача по проекту: агент ищет и читает файлы, затем "
            "отвечает со ссылками. Запись и команды пока запрещены. "
            "Прочитанные файлы уходят провайдеру выбранной модели.",
            self,
        )
        subtitle.setObjectName("dialogHint")
        subtitle.setWordWrap(True)

        self.task_input = QPlainTextEdit(self)
        self.task_input.setObjectName("agentTask")
        self.task_input.setPlaceholderText(
            "Например: как устроена граница модели и агента?"
        )
        self.task_input.setFixedHeight(64)

        self.run_button = QPushButton("Запустить", self)
        self.run_button.setObjectName("workshopAction")
        self.run_button.clicked.connect(self._start)

        self.stop_button = QPushButton("Остановить", self)
        self.stop_button.setObjectName("workshopAction")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._stop)

        self.status_label = QLabel("Готов к задаче.", self)
        self.status_label.setObjectName("dialogHint")
        self.status_label.setWordWrap(True)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(self.run_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.status_label, 1)

        self.trace = QPlainTextEdit(self)
        self.trace.setObjectName("agentTrace")
        self.trace.setReadOnly(True)
        self.trace.setLineWrapMode(QPlainTextEdit.WidgetWidth)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(subtitle)
        self.body_layout.addWidget(self.task_input)
        self.body_layout.addLayout(controls)
        self.body_layout.addWidget(self.trace, 1)
        self.body_layout.addWidget(buttons)

    def _start(self) -> None:
        """Запускает новую задачу агента."""

        if self.job is not None and not self.job.done:
            return

        task = self.task_input.toPlainText().strip()

        if not task:
            self.status_label.setText("Сначала опиши задачу.")
            return

        model = _pick_model()

        if model is None:
            self.status_label.setText(
                "Нет доступной внешней модели: подключи её в окне «Модель»."
            )
            return

        brain = ModelBrain(
            model["model_id"],
            model.get("provider_id") or "opencode",
        )

        self.trace.clear()
        self._shown = 0
        self.job = AgentJob(
            task,
            brain,
            BASE_DIR,
            max_steps=MAX_STEPS,
        )

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText(
            f"Модель: {model['name']} · шагов до {MAX_STEPS}."
        )
        self._timer.start()

    def _stop(self) -> None:
        """Просит агента завершиться после текущего шага."""

        if self.job is None or self.job.done:
            return

        self.job.cancel()
        self.stop_button.setEnabled(False)
        self.status_label.setText("Останавливаю после текущего шага…")

    def _poll(self) -> None:
        """Дорисовывает новые шаги и завершает задачу."""

        job = self.job

        if job is None:
            self._timer.stop()

            return

        while self._shown < len(job.steps):
            step = job.steps[self._shown]
            self._shown += 1

            mark = STEP_MARKS.get(step.kind, "·")
            lines = [f"[{step.index}] {mark} {step.title}"]

            if step.detail:
                lines.append("    " + step.detail)

            self.trace.appendPlainText("\n".join(lines))

        if not job.done:
            self.status_label.setText(
                f"Работаю… шаг {len(job.steps)} из {MAX_STEPS}."
            )

            return

        self._timer.stop()
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        if job.cancelled:
            self.status_label.setText("Остановлено.")
        elif job.error:
            self.status_label.setText(job.error)

            if job.error not in self.trace.toPlainText():
                self.trace.appendPlainText("\n! " + job.error)
        else:
            self.status_label.setText(
                f"Готово за {len(job.steps)} шаг(ов)."
            )

        if job.answer:
            self.trace.appendPlainText("\nОТВЕТ:\n" + job.answer)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Останавливает задачу, чтобы поток не жил после закрытия."""

        if self.job is not None and not self.job.done:
            self.job.cancel()

        self._timer.stop()
        super().closeEvent(event)


def show_agent_dialog(parent) -> None:
    """Открывает немодальное окно агента."""

    dialog = AgentDialog(parent)
    show_tool_window(parent, dialog, "agent")
