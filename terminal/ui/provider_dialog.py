# Giperion/terminal/ui/provider_dialog.py                            v001
# Настройки провайдера агента: адрес, ключ, модель и проверка связи.
# Последнее изменение: первый вариант — локальный файл, проверка в потоке.

import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from terminal.core.agent.providers import (
    OpenAICompatibleProvider,
    ProviderError,
)
from terminal.core.agent.registry import reload_plugins
from terminal.core.agent.settings import (
    allow_unsafe_plugins,
    browser_enabled,
    budget_limits,
    context_limit_chars,
    embedding_model,
    load_settings,
    mask_key,
    mcp_enabled,
    plugin_sandbox,
    plugins_enabled,
    request_timeout,
    save_budget_limits,
    save_settings,
    semantic_enabled,
    set_allow_unsafe_plugins,
    set_browser_enabled,
    set_context_limit_chars,
    set_embedding_model,
    set_mcp_enabled,
    set_plugin_sandbox,
    set_plugins_enabled,
    set_request_timeout,
    set_semantic_enabled,
    set_step_timeout,
    set_stream_enabled,
    step_timeout,
    stream_enabled,
)
from terminal.ui.dialogs_base import SkinDialog, show_tool_window

POLL_MS = 150


class ProviderDialog(SkinDialog):
    """Окно настроек провайдера с проверкой подключения."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Провайдер агента",
            min_width=680,
            min_height=420,
        )

        self._result: tuple[bool, str] | None = None
        self._thread: threading.Thread | None = None

        self._build()

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_MS)
        self._timer.timeout.connect(self._poll)

    def _build(self) -> None:
        """Собирает окно провайдера."""

        title = QLabel("ПРОВАЙДЕР АГЕНТА", self)
        title.setObjectName("dialogTitle")

        hint = QLabel(
            "Нужен OpenAI-совместимый endpoint с /chat/completions и "
            "поддержкой tools. Ключ хранится локально в "
            "data/agent_settings.json и не попадает в git. "
            "Если поля пусты, используется JSON-протокол через OpenCode.",
            self,
        )
        hint.setObjectName("dialogHint")
        hint.setWordWrap(True)

        form = self._build_connection_form()
        self._add_budget_rows(form)
        self._add_option_rows(form)

        self.status_label = QLabel("Готово к настройке.", self)
        self.status_label.setObjectName("dialogHint")
        self.status_label.setWordWrap(True)

        self.check_button = QPushButton("Проверить", self)
        self.check_button.setObjectName("workshopAction")
        self.check_button.clicked.connect(self._check)

        self.save_button = QPushButton("Сохранить", self)
        self.save_button.setObjectName("workshopAction")
        self.save_button.clicked.connect(self._save)

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.check_button)
        row.addWidget(self.save_button)
        row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.button(QDialogButtonBox.Close).setText("Закрыть")
        buttons.rejected.connect(self.reject)

        self.body_layout.addWidget(title)
        self.body_layout.addWidget(hint)
        self.body_layout.addLayout(form)
        self.body_layout.addLayout(row)
        self.body_layout.addWidget(self.status_label, 1)
        self.body_layout.addWidget(buttons)

    def _build_connection_form(self) -> QFormLayout:
        """Адрес, модель и ключ провайдера."""

        values = load_settings()

        self.base_input = QLineEdit(values["base_url"], self)
        self.base_input.setPlaceholderText(
            "https://api.example.com/v1"
        )

        self.model_input = QLineEdit(values["model"], self)
        self.model_input.setPlaceholderText("например, gpt-4.1-mini")

        self.key_input = QLineEdit(values["api_key"], self)
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setPlaceholderText(
            mask_key(values["api_key"]) or "ключ провайдера"
        )

        form = QFormLayout()
        form.setSpacing(6)
        form.addRow("Base URL", self.base_input)
        form.addRow("Модель", self.model_input)
        form.addRow("API-ключ", self.key_input)

        return form

    def _add_budget_rows(self, form: QFormLayout) -> None:
        """Лимиты, цены, таймаут и бюджет контекста."""

        limits = budget_limits()

        self.token_limit_input = QSpinBox(self)
        self.token_limit_input.setRange(0, 100_000_000)
        self.token_limit_input.setSingleStep(10_000)
        self.token_limit_input.setSuffix(" токенов")
        self.token_limit_input.setSpecialValueText("без лимита")
        self.token_limit_input.setValue(int(limits.tokens))

        self.cost_limit_input = QDoubleSpinBox(self)
        self.cost_limit_input.setRange(0.0, 100_000.0)
        self.cost_limit_input.setDecimals(4)
        self.cost_limit_input.setSingleStep(0.1)
        self.cost_limit_input.setPrefix("$ ")
        self.cost_limit_input.setSpecialValueText("без лимита")
        self.cost_limit_input.setValue(float(limits.cost))

        self.price_in_input = QDoubleSpinBox(self)
        self.price_in_input.setRange(0.0, 10_000.0)
        self.price_in_input.setDecimals(3)
        self.price_in_input.setPrefix("$ ")
        self.price_in_input.setSuffix(" / 1M")
        self.price_in_input.setSpecialValueText("бесплатно")
        self.price_in_input.setValue(float(limits.price_in))

        self.price_out_input = QDoubleSpinBox(self)
        self.price_out_input.setRange(0.0, 10_000.0)
        self.price_out_input.setDecimals(3)
        self.price_out_input.setPrefix("$ ")
        self.price_out_input.setSuffix(" / 1M")
        self.price_out_input.setSpecialValueText("бесплатно")
        self.price_out_input.setValue(float(limits.price_out))

        prices_row = QHBoxLayout()
        prices_row.setSpacing(8)
        prices_row.addWidget(QLabel("вход", self))
        prices_row.addWidget(self.price_in_input)
        prices_row.addSpacing(6)
        prices_row.addWidget(QLabel("выход", self))
        prices_row.addWidget(self.price_out_input)
        prices_row.addStretch(1)

        form.addRow("Лимит задачи", self.token_limit_input)
        form.addRow("Лимит стоимости", self.cost_limit_input)
        form.addRow("Цена токенов", prices_row)

        self.timeout_input = QSpinBox(self)
        self.timeout_input.setRange(10, 900)
        self.timeout_input.setSingleStep(10)
        self.timeout_input.setSuffix(" с")
        self.timeout_input.setValue(int(request_timeout()))
        self.timeout_input.setToolTip(
            "Сколько ждать ответа модели на один запрос. "
            "Временные ошибки провайдер повторяет сам."
        )
        form.addRow("Таймаут запроса", self.timeout_input)

        self.step_timeout_input = QSpinBox(self)
        self.step_timeout_input.setRange(0, 3600)
        self.step_timeout_input.setSingleStep(30)
        self.step_timeout_input.setSuffix(" с")
        self.step_timeout_input.setSpecialValueText("без лимита")
        self.step_timeout_input.setValue(int(step_timeout()))
        self.step_timeout_input.setToolTip(
            "Сколько ждать один шаг модели. 0 — без ограничения. "
            "Уже начатый запрос не прерывается, но цикл перестаёт ждать."
        )
        form.addRow("Таймаут шага", self.step_timeout_input)

        self.context_input = QSpinBox(self)
        self.context_input.setRange(8_000, 2_000_000)
        self.context_input.setSingleStep(10_000)
        self.context_input.setSuffix(" символов")
        self.context_input.setValue(int(context_limit_chars()))
        self.context_input.setToolTip(
            "Сколько символов промпта разрешено одной задаче. "
            "Для локальной модели с окном 32k токенов разумно 60–80k "
            "символов."
        )
        form.addRow("Бюджет контекста", self.context_input)

    def _add_option_rows(self, form: QFormLayout) -> None:
        """Плагины, песочница, MCP, веб и поток."""

        self.plugins_check = QCheckBox(
            "Разрешить плагины инструментов",
            self,
        )
        self.plugins_check.setChecked(plugins_enabled())
        self.plugins_check.setToolTip(
            "Плагины из data/agent_tools выполняются в отдельном процессе "
            "с таймаутом, но с правами Терминала. Включай осознанно."
        )
        form.addRow("Плагины", self.plugins_check)

        self.unsafe_check = QCheckBox(
            "Разрешать плагинам сеть и запуск программ",
            self,
        )
        self.unsafe_check.setChecked(allow_unsafe_plugins())
        self.unsafe_check.setToolTip(
            "По умолчанию плагин получает только чтение файлов проекта. "
            "Сеть и запуск программ включаются отдельно и требуют "
            "risk=exec в манифесте."
        )
        form.addRow("Опасные плагины", self.unsafe_check)

        self.sandbox_combo = QComboBox(self)
        self.sandbox_combo.setObjectName("approvalPolicy")
        self.sandbox_combo.addItem("Процесс + сторож", "process")
        self.sandbox_combo.addItem("AppContainer (Windows)", "appcontainer")
        index = self.sandbox_combo.findData(plugin_sandbox())
        self.sandbox_combo.setCurrentIndex(max(0, index))
        self.sandbox_combo.setToolTip(
            "AppContainer изолирует файловую систему и сеть на уровне ОС, "
            "но требует подготовки: python -m tools.setup_plugin_container "
            "--prepare. В этом режиме плагины только читают проект."
        )
        form.addRow("Песочница", self.sandbox_combo)

        self.mcp_check = QCheckBox("Включить MCP-серверы", self)
        self.mcp_check.setChecked(mcp_enabled())
        self.mcp_check.setToolTip(
            "Серверы из data/agent_mcp.json: внешние инструменты по "
            "JSON-RPC через stdio. По умолчанию выключены — см. docs/mcp.md."
        )
        form.addRow("MCP", self.mcp_check)

        self.browser_check = QCheckBox(
            "Разрешить чтение веб-страниц",
            self,
        )
        self.browser_check.setChecked(browser_enabled())
        self.browser_check.setToolTip(
            "Инструмент fetch_url: один GET на http/https, текст без "
            "разметки. Локальные и приватные адреса запрещены. "
            "Каждый новый сайт требует подтверждения."
        )
        form.addRow("Веб", self.browser_check)

        self.semantic_check = QCheckBox(
            "Смысловой поиск по проекту",
            self,
        )
        self.semantic_check.setChecked(semantic_enabled())
        self.semantic_check.setToolTip(
            "Инструмент find_relevant: ищет код и документацию по смыслу "
            "задачи. Эмбеддинги запрашиваются только у локального "
            "провайдера (/embeddings); если его нет — работает поиск по "
            "словам (BM25)."
        )
        form.addRow("Смысловой поиск", self.semantic_check)

        self.embedding_input = QLineEdit(self)
        self.embedding_input.setText(embedding_model())
        self.embedding_input.setPlaceholderText("определить автоматически")
        self.embedding_input.setToolTip(
            "Имя модели эмбеддингов на локальном провайдере, например "
            "text-embedding-nomic-embed-text-v1.5. Пусто — найти модель "
            "в /models по слову embed."
        )
        form.addRow("Модель эмбеддингов", self.embedding_input)

        self.stream_check = QCheckBox(
            "Показывать ответ по мере генерации",
            self,
        )
        self.stream_check.setChecked(stream_enabled())
        self.stream_check.setToolTip(
            "Поток SSE: текст появляется в статусе сразу. Если сервер не "
            "умеет поток, агент молча вернётся к обычному запросу."
        )
        form.addRow("Поток", self.stream_check)

    def _provider(self) -> OpenAICompatibleProvider:
        return OpenAICompatibleProvider(
            self.base_input.text().strip(),
            self.key_input.text().strip(),
            self.model_input.text().strip(),
            timeout=20,
        )

    def _check(self) -> None:
        """Проверяет подключение в отдельном потоке."""

        if self._thread is not None and self._thread.is_alive():
            return

        provider = self._provider()

        if not provider.base_url or not provider.api_key or not provider.model:
            self.status_label.setText("Заполни адрес, модель и ключ.")
            return

        self.check_button.setEnabled(False)
        self.status_label.setText("Проверяю подключение…")
        self._result = None

        def run() -> None:
            try:
                reply = provider.complete(
                    [
                        {
                            "role": "user",
                            "content": "Ответь одним словом: ок",
                        }
                    ]
                )
                text = reply.text.strip() or "пусто"
                self._result = (True, f"Связь есть. Ответ: {text[:80]}")
            except ProviderError as error:
                self._result = (False, str(error))
            except Exception as error:  # noqa: BLE001
                self._result = (
                    False,
                    f"{type(error).__name__}: {error}",
                )

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        self._timer.start()

    def _poll(self) -> None:
        if self._result is None:
            return

        ok, text = self._result
        self._result = None
        self._timer.stop()
        self.check_button.setEnabled(True)
        self.status_label.setText(("✓ " if ok else "✕ ") + text)

    def _save(self) -> None:
        values = save_settings(
            self.base_input.text(),
            self.key_input.text(),
            self.model_input.text(),
        )

        save_budget_limits(
            self.token_limit_input.value(),
            self.cost_limit_input.value(),
            self.price_in_input.value(),
            self.price_out_input.value(),
        )

        set_request_timeout(self.timeout_input.value())
        set_step_timeout(self.step_timeout_input.value())
        set_context_limit_chars(self.context_input.value())

        set_plugins_enabled(self.plugins_check.isChecked())
        set_allow_unsafe_plugins(self.unsafe_check.isChecked())
        set_plugin_sandbox(
            str(self.sandbox_combo.currentData() or "process")
        )
        set_stream_enabled(self.stream_check.isChecked())
        set_mcp_enabled(self.mcp_check.isChecked())
        set_browser_enabled(self.browser_check.isChecked())
        set_semantic_enabled(self.semantic_check.isChecked())
        set_embedding_model(self.embedding_input.text())

        from terminal.core.agent import mcp, semantic

        mcp.reload_mcp()
        semantic.reset_cache()
        reload_plugins()

        if all(values.values()):
            self.status_label.setText(
                "Сохранено. Следующая задача пойдёт через провайдера."
            )
        else:
            self.status_label.setText(
                "Сохранено, но поля неполные — будет JSON-протокол."
            )

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)


def show_provider_dialog(parent) -> None:
    """Открывает немодальные настройки провайдера."""

    dialog = ProviderDialog(parent)
    show_tool_window(parent, dialog, "agent-provider")
