# Giperion/terminal/ui/agent/controls.py                              v001
# Верхняя часть окна агента: задача, шаблон, модель, лимиты и кнопки.
# Последнее изменение: вынесено из agent_dialog.

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from terminal.core.agent.providers import provider_from_settings
from terminal.core.agent.settings import (
    approval_policy,
    context_auto,
    context_limit_chars,
    max_steps,
    model_choice,
)
from terminal.ui.agent.constants import TASK_TEMPLATES


def _available_models() -> list[dict]:
    """Модели каталога, которые можно запустить прямо сейчас."""

    try:
        from terminal.core.model_catalog import load_models

        models = load_models()
    except Exception:  # noqa: BLE001 — без каталога остаётся провайдер
        return []

    return [
        model
        for model in models
        if model.get("available") and model.get("model_id")
    ]


class AgentControls(QWidget):
    """Поля задачи и кнопки управления прогоном."""

    run_requested = Signal()
    stop_requested = Signal()
    pause_requested = Signal()
    new_task_requested = Signal()
    tasks_requested = Signal()
    watch_requested = Signal()
    undo_requested = Signal()
    provider_requested = Signal()
    trace_requested = Signal()
    plan_requested = Signal()
    retry_requested = Signal()
    save_defaults_requested = Signal()
    resume_last_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._build_task(layout)
        layout.addLayout(self._build_model_row())
        layout.addLayout(self._build_limits_row())
        layout.addLayout(self._build_buttons_row())

    def _build_task(self, layout: QVBoxLayout) -> None:
        """Поле задачи и выбор шаблона."""

        self.task_input = QPlainTextEdit(self)
        self.task_input.setObjectName("agentTask")
        self.task_input.setPlaceholderText(
            "Например: как устроена граница модели и агента?"
        )
        self.task_input.setFixedHeight(64)

        self.template_combo = QComboBox(self)
        self.template_combo.setObjectName("approvalPolicy")
        self.template_combo.setToolTip(
            "Готовые формулировки задач: выбери — текст подставится."
        )
        self.template_combo.addItem("Шаблон задачи…", "")

        for template_title, template_text in TASK_TEMPLATES:
            self.template_combo.addItem(template_title, template_text)

        self.template_combo.currentIndexChanged.connect(
            self._apply_template
        )

        layout.addWidget(self.task_input)
        layout.addWidget(self.template_combo)

    def _build_model_row(self) -> QHBoxLayout:
        """Ветка, провайдер и политика подтверждений."""

        self.worktree_checkbox = QCheckBox(
            "Отдельная ветка (worktree)",
            self,
        )
        self.worktree_checkbox.setToolTip(
            "Создать отдельное рабочее дерево и ветку agent/…, "
            "чтобы не мешать другим задачам."
        )

        self.provider_button = QPushButton("Провайдер…", self)
        self.provider_button.setObjectName("workshopAction")
        self.provider_button.setToolTip(
            "Адрес, ключ и модель провайдера с настоящими tool calls."
        )
        self.provider_button.clicked.connect(
            self.provider_requested.emit
        )

        self.policy_combo = QComboBox(self)
        self.policy_combo.setObjectName("approvalPolicy")
        self.policy_combo.addItem("Спрашивать всё", "confirm")
        self.policy_combo.addItem("Доверять правкам", "trust")
        self.policy_combo.addItem("Только чтение", "read")
        self.policy_combo.setToolTip(
            "Только чтение — запись запрещена; "
            "Доверять правкам — apply_patch и запись без вопросов, "
            "но команды и коммиты всё равно спрашивают."
        )

        current_policy = approval_policy()
        policy_index = self.policy_combo.findData(current_policy)

        if policy_index >= 0:
            self.policy_combo.setCurrentIndex(policy_index)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.worktree_checkbox)
        row.addWidget(self.provider_button)
        row.addWidget(self.policy_combo)
        row.addStretch(1)

        return row

    def _build_limits_row(self) -> QHBoxLayout:
        """Модель, лимит шагов и бюджет контекста."""

        self.steps_input = QSpinBox(self)
        self.steps_input.setRange(1, 40)
        self.steps_input.setValue(int(max_steps()))
        self.steps_input.setSuffix(" шагов")
        self.steps_input.setToolTip(
            "Сколько решений модели разрешено одной задаче."
        )

        self.context_input = QSpinBox(self)
        self.context_input.setRange(8_000, 2_000_000)
        self.context_input.setSingleStep(10_000)
        self.context_input.setSuffix(" симв.")
        self.context_input.setValue(int(context_limit_chars()))
        self.context_input.setToolTip(
            "Бюджет контекста задачи в символах."
        )

        self.auto_context_check = QCheckBox("Из модели", self)
        self.auto_context_check.setChecked(context_auto())
        self.auto_context_check.setToolTip(
            "Считать бюджет из контекста выбранной модели. "
            "Если модель неизвестна, берётся значение из поля."
        )

        self.model_combo = QComboBox(self)
        self.model_combo.setObjectName("approvalPolicy")
        self.model_combo.setMinimumWidth(230)
        self.model_combo.setToolTip(
            "Какой моделью выполнять задачу: провайдер из настроек "
            "или модель каталога."
        )
        self._fill_models()

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.model_combo)
        row.addWidget(self.steps_input)
        row.addWidget(self.context_input)
        row.addWidget(self.auto_context_check)

        self.save_defaults_button = QPushButton("Запомнить", self)
        self.save_defaults_button.setObjectName("workshopAction")
        self.save_defaults_button.setToolTip(
            "Использовать эти модель, шаги и контекст по умолчанию "
            "для новых окон агента."
        )
        self.save_defaults_button.clicked.connect(
            self.save_defaults_requested.emit
        )
        row.addWidget(self.save_defaults_button)
        row.addStretch(1)

        return row

    def _build_buttons_row(self) -> QHBoxLayout:
        """Кнопки прогона, задач, наблюдателя и статус."""

        self.run_button = QPushButton("Запустить", self)
        self.run_button.setObjectName("workshopAction")
        self.run_button.clicked.connect(self.run_requested.emit)

        self.stop_button = QPushButton("Остановить", self)
        self.stop_button.setObjectName("workshopAction")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_requested.emit)

        self.new_task_button = QPushButton("Новая задача", self)
        self.new_task_button.setObjectName("workshopAction")
        self.new_task_button.setToolTip(
            "Открыть ещё одно окно агента и запустить задачу параллельно."
        )
        self.new_task_button.clicked.connect(
            self.new_task_requested.emit
        )

        self.tasks_button = QPushButton("Задачи…", self)
        self.tasks_button.setObjectName("workshopAction")
        self.tasks_button.setToolTip(
            "Сохранённые задачи: продолжить или удалить."
        )
        self.tasks_button.clicked.connect(self.tasks_requested.emit)

        self.undo_button = QPushButton("Откатить изменения", self)
        self.undo_button.setObjectName("workshopAction")
        self.undo_button.setVisible(False)
        self.undo_button.setToolTip(
            "Вернуть файлы задачи к состоянию до её запуска."
        )
        self.undo_button.clicked.connect(self.undo_requested.emit)

        self.watch_button = QPushButton("Наблюдатель…", self)
        self.watch_button.setObjectName("workshopAction")
        self.watch_button.setToolTip(
            "Следить за файлами проекта и запускать проверку по изменениям."
        )
        self.watch_button.clicked.connect(self.watch_requested.emit)

        self.trace_button = QPushButton("Трейс…", self)
        self.trace_button.setObjectName("workshopAction")
        self.trace_button.setEnabled(False)
        self.trace_button.setToolTip(
            "Полный трейс задачи в отдельном окне."
        )
        self.trace_button.clicked.connect(self.trace_requested.emit)

        self.plan_button = QPushButton("План…", self)
        self.plan_button.setObjectName("workshopAction")
        self.plan_button.setToolTip(
            "Чек-лист текущей задачи: что сделано и что осталось."
        )
        self.plan_button.clicked.connect(self.plan_requested.emit)

        self.retry_button = QPushButton("С шага…", self)
        self.retry_button.setObjectName("workshopAction")
        self.retry_button.setToolTip(
            "Повторить задачу с выбранного шага и другим указанием. "
            "Контекст откатится, файлы — нет."
        )
        self.retry_button.clicked.connect(self.retry_requested.emit)

        self.pause_button = QPushButton("Пауза", self)
        self.pause_button.setObjectName("workshopAction")
        self.pause_button.setEnabled(False)
        self.pause_button.setToolTip(
            "Пауза после текущего шага; повторное нажатие продолжает."
        )
        self.pause_button.clicked.connect(self.pause_requested.emit)

        self.resume_last_button = QPushButton(
            "Продолжить незавершённую",
            self,
        )
        self.resume_last_button.setObjectName("workshopAction")
        self.resume_last_button.setVisible(False)
        self.resume_last_button.setToolTip(
            "Открыть сохранённую незавершённую задачу с её историей."
        )
        self.resume_last_button.clicked.connect(
            self.resume_last_requested.emit
        )

        self.status_label = QLabel("Готов к задаче.", self)
        self.status_label.setObjectName("dialogHint")
        self.status_label.setWordWrap(True)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.run_button)
        row.addWidget(self.stop_button)
        row.addWidget(self.pause_button)
        row.addWidget(self.new_task_button)
        row.addWidget(self.tasks_button)
        row.addWidget(self.resume_last_button)
        row.addWidget(self.watch_button)
        row.addWidget(self.trace_button)
        row.addWidget(self.plan_button)
        row.addWidget(self.retry_button)
        row.addWidget(self.undo_button)
        row.addWidget(self.status_label, 1)

        return row

    def _apply_template(self, index: int) -> None:
        """Подставляет текст шаблона в поле задачи."""

        text = str(self.template_combo.itemData(index) or "")

        if not text:
            return

        self.task_input.setPlainText(text)
        self.task_input.setFocus()

        self.template_combo.blockSignals(True)
        self.template_combo.setCurrentIndex(0)
        self.template_combo.blockSignals(False)

    def _fill_models(self) -> None:
        """Заполняет список моделей: провайдер и каталог."""

        self.model_combo.clear()
        saved = model_choice()
        native = provider_from_settings()

        if native is not None:
            self.model_combo.addItem(
                f"Провайдер · {native.model}",
                {"kind": "native"},
            )

        for model in _available_models():
            label = str(model.get("name") or model.get("model_id"))
            self.model_combo.addItem(
                label[:60],
                {"kind": "model", "model": model},
            )

        if self.model_combo.count() == 0:
            self.model_combo.addItem("Нет доступных моделей", None)

            return

        index = 0

        for position in range(self.model_combo.count()):
            data = self.model_combo.itemData(position)

            if not isinstance(data, dict):
                continue

            if data.get("kind") == "native" and saved in ("", "native"):
                index = position

                break

            if (
                data.get("kind") == "model"
                and saved == str((data.get("model") or {}).get("id") or "")
            ):
                index = position

                break

        self.model_combo.setCurrentIndex(index)

    @property
    def task_text(self) -> str:
        """Текст задачи без пробелов по краям."""

        return self.task_input.toPlainText().strip()

    @property
    def policy(self) -> str:
        """Выбранная политика подтверждений."""

        return self.policy_combo.currentData() or "confirm"

    @property
    def model_choice(self):
        """Данные выбранной модели."""

        return self.model_combo.currentData()

    @property
    def steps_limit(self) -> int:
        """Лимит шагов задачи."""

        return int(self.steps_input.value())

    @property
    def context_chars(self) -> int:
        """Бюджет контекста задачи."""

        return int(self.context_input.value())

    @property
    def worktree_enabled(self) -> bool:
        """Нужна ли отдельная ветка."""

        return self.worktree_checkbox.isChecked()
