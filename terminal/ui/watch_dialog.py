# Giperion/terminal/ui/watch_dialog.py                                 v001
# Окно «Наблюдатель»: слежение за файлами и запуск read-only задачи.

import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from config import BASE_DIR
from terminal.core.agent.brain import ModelBrain
from terminal.core.agent.providers import NativeBrain
from terminal.core.agent.settings import (
    budget_limits,
    context_limit_chars,
    provider_from_settings,
)
from terminal.core.agent.watch import (
    Changes,
    Watcher,
    WatchSettings,
    load_settings,
    save_settings,
)
from terminal.ui.agent_job import AgentJob
from terminal.ui.dialogs_base import SkinDialog, show_tool_window

POLL_MS = 500


class WatchDialog(SkinDialog):
    """Следит за файлами проекта и по паузе запускает проверку."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Наблюдатель",
            min_width=760,
            min_height=520,
        )

        self.watcher: Watcher | None = None
        self.job: AgentJob | None = None
        self._pending: Changes | None = None
        self._last_run = 0.0

        values = load_settings()
        self._settings_value = values

        title = QLabel("НАБЛЮДАТЕЛЬ ЗА ФАЙЛАМИ", self)
        title.setObjectName("dialogTitle")

        hint = QLabel(
            "Раз в несколько секунд смотрит на файлы проекта. Когда "
            "изменения утихнут, пишет их в журнал и — если включено — "
            "запускает задачу только на чтение. Служебные папки "
            "(data, .git, worktrees) не наблюдаются.",
            self,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        self.interval_input = QSpinBox(self)
        self.interval_input.setRange(1, 120)
        self.interval_input.setSuffix(" с")
        self.interval_input.setValue(int(values.interval_s))

        self.debounce_input = QSpinBox(self)
        self.debounce_input.setRange(0, 60)
        self.debounce_input.setSuffix(" с")
        self.debounce_input.setValue(int(values.debounce_s))

        self.cooldown_input = QSpinBox(self)
        self.cooldown_input.setRange(0, 600)
        self.cooldown_input.setSuffix(" с")
        self.cooldown_input.setValue(int(values.cooldown_s))

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(QLabel("Опрос", self))
        row.addWidget(self.interval_input)
        row.addWidget(QLabel("Пауза", self))
        row.addWidget(self.debounce_input)
        row.addWidget(QLabel("Отдых", self))
        row.addWidget(self.cooldown_input)
        row.addStretch(1)

        self.task_input = QPlainTextEdit(self)
        self.task_input.setObjectName("agentTask")
        self.task_input.setFixedHeight(64)
        self.task_input.setPlainText(values.task)

        self.auto_check = QCheckBox(
            "Запускать задачу автоматически (только чтение)",
            self,
        )
        self.auto_check.setChecked(values.auto_run)

        self.start_button = QPushButton("Начать наблюдение", self)
        self.start_button.setObjectName("workshopAction")
        self.start_button.clicked.connect(self._toggle)

        self.log = QPlainTextEdit(self)
        self.log.setObjectName("agentTrace")
        self.log.setReadOnly(True)

        self.status_label = QLabel("Наблюдение выключено.", self)
        self.status_label.setObjectName("dialogHint")
        self.status_label.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(hint)
        self.body_layout.addLayout(row)
        self.body_layout.addWidget(QLabel("Задача на изменения:", self))
        self.body_layout.addWidget(self.task_input)
        self.body_layout.addWidget(self.auto_check)
        self.body_layout.addLayout(
            self._button_row(self.start_button)
        )
        self.body_layout.addWidget(self.log, 1)
        self.body_layout.addWidget(self.status_label)
        self.body_layout.addWidget(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

    @staticmethod
    def _button_row(*buttons) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        for button in buttons:
            row.addWidget(button)

        row.addStretch(1)

        return row

    def _settings(self) -> WatchSettings:
        return WatchSettings(
            enabled=True,
            interval_s=float(self.interval_input.value()),
            debounce_s=float(self.debounce_input.value()),
            cooldown_s=float(self.cooldown_input.value()),
            task=self.task_input.toPlainText().strip()
            or WatchSettings.task,
            auto_run=self.auto_check.isChecked(),
        )

    def _toggle(self) -> None:
        """Включает или выключает наблюдение."""

        if self.watcher is not None:
            self._stop()
            return

        self._settings_value = self._settings()
        save_settings(self._settings_value)

        self.watcher = Watcher(
            BASE_DIR,
            interval_s=self._settings_value.interval_s,
            debounce_s=self._settings_value.debounce_s,
            cooldown_s=self._settings_value.cooldown_s,
        )
        self.watcher.start(
            on_change=self._on_change,
            on_error=self._on_error,
        )
        self._timer.start()
        self.start_button.setText("Остановить")
        self.status_label.setText(
            "Наблюдаю за проектом. Изменения появятся здесь."
        )
        self.log.appendPlainText(
            f"[{self._now()}] наблюдение начато · "
            f"опрос {self._settings_value.interval_s:g} с"
        )

    def _stop(self) -> None:
        """Останавливает наблюдение и текущую задачу."""

        if self.watcher is not None:
            self.watcher.stop()
            self.watcher = None

        if self.job is not None and not self.job.done:
            self.job.cancel()

        self.job = None
        self._timer.stop()
        self.start_button.setText("Начать наблюдение")
        self.status_label.setText("Наблюдение выключено.")

    def _on_change(self, changes: Changes) -> None:
        """Приходит из потока наблюдателя: только складываем."""

        self._pending = changes

    def _on_error(self, error: Exception) -> None:
        self._pending = Changes(modified=[f"ошибка: {error}"])

    def _poll(self) -> None:
        """Обрабатывает изменения и завершение задачи в потоке окна."""

        if self._pending is not None:
            changes = self._pending
            self._pending = None
            self._handle(changes)

        job = self.job

        if job is not None and job.done:
            self.job = None
            text = job.answer or job.error or "без ответа"
            self.log.appendPlainText(
                f"[{self._now()}] задача · {len(job.steps)} шагов · "
                f"{job.duration_s:.1f} с\n{text[:600]}"
            )
            self.status_label.setText("Задача по изменениям завершена.")

    def _handle(self, changes: Changes) -> None:
        """Пишет изменения в журнал и запускает задачу, если включено."""

        self.log.appendPlainText(
            f"[{self._now()}] изменения ({changes.total()}):\n"
            + changes.summary()
        )

        if not self._settings_value.auto_run:
            self.status_label.setText(
                "Изменения записаны. Авто-запуск выключен."
            )

            return

        if self.job is not None and not self.job.done:
            self.status_label.setText(
                "Изменения записаны, предыдущая задача ещё идёт."
            )

            return

        brain, model_name = self._brain()

        if brain is None:
            self.status_label.setText(
                "Нет модели для авто-запуска: настрой провайдера."
            )

            return

        task = (
            self._settings_value.task
            + "\n\nЧто изменилось:\n"
            + changes.summary()
        )

        self.job = AgentJob(
            task,
            brain,
            BASE_DIR,
            max_steps=4,
            model_name=model_name,
            policy="read",
            persist=False,
            budget=budget_limits(),
            max_prompt_chars=context_limit_chars(),
        )
        self._last_run = time.monotonic()
        self.status_label.setText("Запущена проверка изменений…")

    def _brain(self):
        """Мозг для авто-запуска: провайдер или модель-помощник."""

        native = provider_from_settings()

        if native is not None:
            return NativeBrain(
                native,
                budget_limits(),
            ), f"native · {native.model}"

        try:
            from terminal.core.helper_model import get_helper_model

            helper = get_helper_model()
        except Exception:  # noqa: BLE001 — помощник не обязателен
            helper = None

        if helper is None:
            return None, ""

        return (
            ModelBrain(
                helper["model_id"],
                helper.get("provider_id") or "opencode",
            ),
            helper["name"],
        )

    @staticmethod
    def _now() -> str:
        return time.strftime("%H:%M:%S")

    def closeEvent(self, event) -> None:
        """Останавливает наблюдение при закрытии окна."""

        self._stop()
        super().closeEvent(event)


def show_watch_dialog(parent) -> None:
    """Открывает немодальное окно наблюдателя."""

    dialog = WatchDialog(parent)
    show_tool_window(parent, dialog, "agent-watch")
