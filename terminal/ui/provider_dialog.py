# Giperion/terminal/ui/provider_dialog.py                            v001
# Настройки провайдера агента: адрес, ключ, модель и проверка связи.
# Последнее изменение: первый вариант — локальный файл, проверка в потоке.

import threading

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from terminal.core.agent.providers import (
    OpenAICompatibleProvider,
    ProviderError,
)
from terminal.core.agent.registry import reload_plugins
from terminal.core.agent.settings import (
    load_settings,
    mask_key,
    plugins_enabled,
    save_settings,
    set_plugins_enabled,
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

        set_plugins_enabled(self.plugins_check.isChecked())
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
