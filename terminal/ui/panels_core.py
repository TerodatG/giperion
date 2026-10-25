# Giperion/terminal/ui/panels_core.py                                  v001
# Панель ядра: рост, закладка «Терминал» и показатели агента.
# Последнее изменение: вынесено из panels_mixin.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from terminal.core.agent_stats import (
    format_cost,
    format_duration,
    read_agent_stats,
)
from terminal.ui.tab_strip import TabStrip
from terminal.ui.value_text import format_tokens
from terminal.ui.widgets import LedMeter, StatusLed


class CorePanelMixin:
    """Часть панелей окна."""

    def _build_core_growth(self) -> None:
        """Переносит «Рост ядра» в параметры ИИ."""

        panel = self.window.personalityPanel
        grid = panel.findChild(QGridLayout, "gridLayout")

        if grid is None:
            return

        self.led_caption = QLabel("РОСТ ЯДРА", panel)
        self.led_caption.setObjectName("growthCaption")
        self.led_caption.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )

        self.status_led = StatusLed(panel)
        self.led_meter = LedMeter(panel)
        self.led_meter.setFixedSize(112, 20)

        meter_row = QHBoxLayout()
        meter_row.setContentsMargins(0, 0, 0, 0)
        meter_row.setSpacing(8)
        meter_row.addWidget(self.status_led)
        meter_row.addWidget(self.led_meter)
        meter_row.addStretch(1)

        # Узкая левая панель: строки параметров получают больше места
        # по вертикали, а шкала роста теперь идёт слева направо.
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(1, 1)

        grid.addWidget(self.led_caption, 8, 0)
        grid.addLayout(meter_row, 8, 1)

        content = grid.parentWidget()

        if content is not None and panel.layout() is None:
            content.setObjectName("personalityContent")
            content.setAttribute(Qt.WA_StyledBackground, False)

            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(14, 10, 14, 12)
            panel_layout.setSpacing(5)

            # Заголовок панели уступает место верхним закладкам.
            self.personality_title.hide()

            self.core_tabs = QTabWidget(panel)
            self.core_tabs.setObjectName("coreTabs")
            self.core_tabs.setDocumentMode(True)
            self.core_tabs.tabBar().hide()

            params_page = QWidget(self.core_tabs)
            params_layout = QVBoxLayout(params_page)
            params_layout.setContentsMargins(0, 0, 0, 0)
            params_layout.setSpacing(0)
            params_layout.addWidget(content)

            executive_page = self._build_executive_page()
            system_page = self._build_system_page()

            self.core_tabs.addTab(params_page, "ИИ")
            self.core_tabs.addTab(
                executive_page,
                "ТЕРМИНАЛ",
            )
            self.core_tabs.addTab(system_page, "СИСТЕМА")

            # Своя полоса закладок: равные кнопки без промежутков.
            self.core_tab_strip = TabStrip(
                panel,
                ("ИИ", "ТЕРМИНАЛ", "СИСТЕМА"),
            )
            self.core_tab_group = self.core_tab_strip.group
            self.core_tab_strip.tab_selected.connect(
                self.core_tabs.setCurrentIndex
            )
            self.core_tabs.currentChanged.connect(
                self._on_core_tab_changed
            )

            panel_layout.addWidget(self.core_tab_strip)
            panel_layout.addWidget(self.core_tabs, 1)

    def _build_executive_page(self) -> QWidget:
        """Собирает закладку агента: числа работы и роста терминала."""

        page = QWidget(self.window.personalityPanel)
        page.setObjectName("executivePage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(8)

        caption = QLabel("ТЕРМИНАЛ", page)
        caption.setObjectName("executiveCaption")

        description = QLabel(
            "Исполнительное ядро: прогоны, инструменты и развитие агента.",
            page,
        )
        description.setObjectName("executiveHint")
        description.setWordWrap(True)

        scroll = QScrollArea(page)
        scroll.setObjectName("systemScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content.setObjectName("systemContent")

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        # --- Рост: уровень и опыт ---
        growth = QWidget(content)
        growth.setObjectName("executiveGrowth")
        growth.setAttribute(Qt.WA_StyledBackground, True)

        growth_layout = QVBoxLayout(growth)
        growth_layout.setContentsMargins(10, 8, 10, 9)
        growth_layout.setSpacing(4)

        self.executive_level = QLabel("УРОВЕНЬ 1", growth)
        self.executive_level.setObjectName("executiveLevel")

        self.executive_bar = QProgressBar(growth)
        self.executive_bar.setObjectName("executiveBar")
        self.executive_bar.setRange(0, 100)
        self.executive_bar.setTextVisible(False)
        self.executive_bar.setFixedHeight(8)

        self.executive_xp = QLabel("", growth)
        self.executive_xp.setObjectName("executiveHint")
        self.executive_xp.setWordWrap(True)

        growth_layout.addWidget(self.executive_level)
        growth_layout.addWidget(self.executive_bar)
        growth_layout.addWidget(self.executive_xp)

        content_layout.addWidget(growth)

        self.executive_values = {}

        def section(
            title: str,
            rows: tuple[tuple[str, str], ...],
        ) -> None:
            """Добавляет группу параметров с подписью."""

            header = QLabel(title, content)
            header.setObjectName("infoCaption")
            content_layout.addWidget(header)

            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 2)
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(4)
            grid.setColumnStretch(1, 1)

            for index, (key, name) in enumerate(rows):
                name_label = QLabel(f"{name}:", content)
                name_label.setObjectName("executiveName")
                name_label.setWordWrap(True)

                value_label = QLabel("—", content)
                value_label.setObjectName("executiveValue")
                value_label.setWordWrap(True)
                value_label.setAlignment(
                    Qt.AlignRight | Qt.AlignVCenter
                )

                grid.addWidget(name_label, index, 0)
                grid.addWidget(value_label, index, 1)

                self.executive_values[key] = value_label

            content_layout.addLayout(grid)

        section(
            "РАБОТА",
            (
                ("runs", "Прогонов"),
                ("ok", "Успешных"),
                ("success", "Успешность"),
                ("steps", "Шагов"),
                ("files", "Файлов изменено"),
                ("approvals", "Подтверждений"),
            ),
        )

        section(
            "РЕСУРСЫ",
            (
                ("duration", "В работе"),
                ("average", "Среднее время"),
                ("tokens", "Токенов"),
                ("cost", "Стоимость"),
            ),
        )

        section(
            "АРСЕНАЛ",
            (
                ("tools", "Инструментов"),
                ("plugins", "Плагинов"),
                ("mcp", "MCP-серверов"),
                ("skills", "Навыков"),
            ),
        )

        self.executive_footer = QLabel("", content)
        self.executive_footer.setObjectName("executiveHint")
        self.executive_footer.setWordWrap(True)

        content_layout.addWidget(self.executive_footer)
        content_layout.addStretch(1)

        scroll.setWidget(content)

        layout.addWidget(caption)
        layout.addWidget(description)
        layout.addWidget(scroll, 1)

        self.update_executive_panel()

        return page

    def update_executive_panel(self) -> None:
        """Обновляет числа развития агента в закладке «Терминал»."""

        if not hasattr(self, "executive_values"):
            return

        stats = read_agent_stats()

        self.executive_level.setText(f"УРОВЕНЬ {stats['level']}")
        self.executive_bar.setValue(stats["level_progress"])
        self.executive_xp.setText(
            f"опыт {format_tokens(stats['experience'])} · "
            f"до следующего уровня "
            f"{format_tokens(stats['to_next_level'])}"
        )

        values = {
            "runs": str(stats["runs_total"]),
            "ok": str(stats["runs_ok"]),
            "success": f"{stats['success_percent']} %",
            "steps": format_tokens(stats["steps_total"]),
            "files": str(stats["files_total"]),
            "approvals": str(stats["approvals_total"]),
            "duration": format_duration(stats["duration_total"]),
            "average": format_duration(stats["duration_average"]),
            "tokens": format_tokens(stats["tokens_total"]),
            "cost": format_cost(stats["cost_total"]),
            "tools": str(stats["tools_builtin"]),
            "plugins": str(stats["plugins"]),
            "mcp": str(stats["mcp_servers"]),
            "skills": str(stats["skills"]),
        }

        for key, value in values.items():
            label = self.executive_values.get(key)

            if label is not None:
                label.setText(value)

        if stats["last_run"]:
            self.executive_footer.setText(
                f"Последний прогон: {stats['last_run']}."
            )
        else:
            self.executive_footer.setText(
                "Прогонов ещё не было: запусти агента в «Мастерской»."
            )

    def _on_core_tab_changed(self, index: int) -> None:
        """Обновляет числа агента при открытии его закладки."""

        if index == 1:
            self.update_executive_panel()
