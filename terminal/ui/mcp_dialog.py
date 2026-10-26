# Giperion/terminal/ui/mcp_dialog.py                                   v001
# Редактор data/agent_mcp.json: серверы, tools и domains.
# Последнее изменение: первый вариант — JSON, проверка и перезагрузка.

import json

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from shared.storage.json_store import read_json_object, write_json
from terminal.core.agent import mcp
from terminal.ui.dialogs_base import SkinDialog, show_tool_window


class McpDialog(SkinDialog):
    """Редактирует конфиг MCP-серверов с проверкой JSON."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "MCP-серверы",
            min_width=720,
            min_height=460,
        )

        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel(
            "Серверы, их команды и allowlist. Поля tools/domains можно "
            "оставить пустыми: пустой tools разрешает все инструменты, "
            "пустой domains — любые URL.",
            self,
        )
        hint.setWordWrap(True)
        hint.setObjectName("dialogHint")
        layout.addWidget(hint)

        self.editor = QPlainTextEdit(self)
        self.editor.setTabStopDistance(28)
        self.editor.setPlainText(
            json.dumps(
                read_json_object(mcp.CONFIG_FILE),
                ensure_ascii=False,
                indent=2,
            )
        )
        layout.addWidget(self.editor, 1)

        self.status = QLabel("", self)
        self.status.setObjectName("dialogHint")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        check = QPushButton("Проверить", self)
        check.clicked.connect(self._check_servers)
        save = QPushButton("Проверить и сохранить", self)
        save.clicked.connect(self._save)
        close = QPushButton("Закрыть", self)
        close.clicked.connect(self.close)
        row.addWidget(check)
        row.addWidget(save)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)

    def _check_servers(self) -> None:
        """Запускает серверы и показывает число инструментов и ресурсов."""

        self.status.setText("Проверяю серверы…")
        self.status.repaint()

        rows = mcp.probe_all()

        if not rows:
            self.status.setText("Серверы не настроены.")

            return

        parts = []

        for row in rows:
            if row["ok"]:
                parts.append(
                    f"{row['name']}: инструментов {row['tools']}, "
                    f"ресурсов {row['resources']}"
                )
            else:
                parts.append(f"{row['name']}: ошибка — {row['error']}")

        self.status.setText(" · ".join(parts))

    def _save(self) -> None:
        """Проверяет JSON, пишет файл и перезагружает MCP."""

        try:
            document = json.loads(self.editor.toPlainText())
        except json.JSONDecodeError as error:
            self.status.setText(f"JSON не разобрался: {error}")

            return

        if not isinstance(document, dict):
            self.status.setText("Нужен объект с ключом servers.")

            return

        servers = document.get("servers")

        if not isinstance(servers, list):
            self.status.setText("Поле servers должно быть списком.")

            return

        parsed = mcp.load_servers(document)

        write_json(mcp.CONFIG_FILE, document)
        mcp.reload_mcp()

        self.status.setText(
            f"Сохранено серверов: {len(parsed)}. "
            "Инструменты перечитаются в следующей задаче."
        )


def show_mcp_dialog(parent) -> None:
    """Открывает редактор MCP немодальным окном."""

    dialog = McpDialog(parent)
    show_tool_window(parent, dialog, "agent-mcp")
