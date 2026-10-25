# Giperion/terminal/ui/view_settings.py                                v001
# Панель «Вид»: шрифт, роли, цвета, стили и параметры ответа.
# Последнее изменение: вынесено из settings_dialog.

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from terminal.core.window_settings import (
    DEFAULT_FONT_SIZES,
    DEFAULT_RESPONSE_SETTINGS,
    DEFAULT_STYLES,
)
from terminal.ui.theme import (
    MAX_CHAT_FONT_SIZE,
    MIN_CHAT_FONT_SIZE,
    TYPING_SPEEDS,
)


class ViewSettingsPanel(QWidget):
    """Страница «Вид»: две кнопки — «Шрифт» и «Ответ ИИ»."""

    COLOR_ROLES = (
        ("system", "Система"),
        ("bot", "Гиперион"),
        ("external", "Внешние модели"),
        ("senator1", "Сенатор 1"),
        ("senator2", "Сенатор 2"),
        ("senator3", "Сенатор 3"),
        ("user", "Пользователь"),
        ("message", "Сообщения"),
        ("data", "Данные (файлы и интернет)"),
    )

    STYLE_OPTIONS = (
        ("normal", "Обычный"),
        ("bold", "Жирный"),
        ("italic", "Курсив"),
        ("bold_italic", "Жирный курсив"),
    )

    def __init__(
        self,
        parent,
        chat_font_family: str,
        chat_font_size: int,
        colors: dict[str, str],
        styles: dict[str, str] | None = None,
        response_settings: dict | None = None,
        font_sizes: dict[str, int] | None = None,
    ) -> None:
        super().__init__(parent)

        self.colors = dict(colors)
        self.styles = {
            **DEFAULT_STYLES,
            **dict(styles or {}),
        }
        self.response_values = {
            **DEFAULT_RESPONSE_SETTINGS,
            **dict(response_settings or {}),
        }
        self.font_sizes = {
            **DEFAULT_FONT_SIZES,
            **dict(font_sizes or {}),
        }

        application = QApplication.instance()
        fallback_family = (
            application.font().family()
            if application is not None
            else ""
        )
        self.font_family = chat_font_family or fallback_family
        self.font_size = int(chat_font_size)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        sections_row = QHBoxLayout()
        sections_row.setSpacing(6)

        self.font_section_button = QPushButton("ШРИФТ", self)
        self.font_section_button.setObjectName("viewSectionButton")
        self.font_section_button.setCheckable(True)
        self.font_section_button.setCursor(Qt.ArrowCursor)
        self.font_section_button.setMinimumHeight(34)

        self.response_section_button = QPushButton("ОТВЕТ ИИ", self)
        self.response_section_button.setObjectName("viewSectionButton")
        self.response_section_button.setCheckable(True)
        self.response_section_button.setCursor(Qt.ArrowCursor)
        self.response_section_button.setMinimumHeight(34)

        self.section_group = QButtonGroup(self)
        self.section_group.setExclusive(True)
        self.section_group.addButton(self.font_section_button, 0)
        self.section_group.addButton(self.response_section_button, 1)

        sections_row.addWidget(self.font_section_button)
        sections_row.addWidget(self.response_section_button)
        sections_row.addStretch(1)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self._build_font_page())
        self.stack.addWidget(self._build_response_page())

        self.font_section_button.setChecked(True)

        self.section_group.idClicked.connect(self.stack.setCurrentIndex)

        root.addLayout(sections_row)
        root.addWidget(self.stack, 1)

    def _build_font_page(self) -> QWidget:
        """Собирает поля гарнитуры, размера, цвета и стиля."""

        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.font_family_combo = QFontComboBox(page)
        self.font_family_combo.setCurrentFont(QFont(self.font_family))
        self.font_family_combo.setMinimumWidth(320)

        self.font_size_input = QSpinBox(page)
        self.font_size_input.setRange(
            MIN_CHAT_FONT_SIZE,
            MAX_CHAT_FONT_SIZE,
        )
        self.font_size_input.setValue(self.font_size)
        self.font_size_input.setSuffix(" pt")

        self.color_role_combo = QComboBox(page)

        for key, title in self.COLOR_ROLES:
            self.color_role_combo.addItem(title, key)

        self.role_font_size_input = QSpinBox(page)
        self.role_font_size_input.setRange(0, MAX_CHAT_FONT_SIZE)
        self.role_font_size_input.setSpecialValueText("как у всего чата")
        self.role_font_size_input.setSuffix(" pt")
        self.role_font_size_input.setToolTip(
            "Свой размер шрифта для выбранной группы. "
            "Ноль — общий размер терминала связи."
        )

        self.color_swatch_button = QPushButton(page)
        self.color_swatch_button.setMinimumHeight(30)
        self.color_swatch_button.setCursor(Qt.ArrowCursor)
        self.color_swatch_button.clicked.connect(self._pick_color)

        self.style_combo = QComboBox(page)

        for style, title in self.STYLE_OPTIONS:
            self.style_combo.addItem(title, style)

        form.addRow("Гарнитура шрифта", self.font_family_combo)
        form.addRow("Размер шрифта", self.font_size_input)
        form.addRow("Группа текста", self.color_role_combo)
        form.addRow("Размер группы", self.role_font_size_input)
        form.addRow("Цвет шрифта", self.color_swatch_button)
        form.addRow("Стиль шрифта", self.style_combo)

        preview_caption = QLabel("ПРЕДПРОСМОТР", page)
        preview_caption.setObjectName("settingsSection")

        self.preview_label = QLabel(
            "Гиперион: так будет выглядеть выбранный текст.",
            page,
        )
        self.preview_label.setObjectName("fontPreview")
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumHeight(76)
        self.preview_label.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        layout.addLayout(form)
        layout.addWidget(preview_caption)
        layout.addWidget(self.preview_label)
        layout.addStretch(1)

        self._load_role_controls()

        self.font_family_combo.currentFontChanged.connect(
            self._font_family_changed
        )
        self.font_size_input.valueChanged.connect(
            self._font_size_changed
        )
        self.color_role_combo.currentIndexChanged.connect(
            self._role_changed
        )
        self.role_font_size_input.valueChanged.connect(
            self._role_font_size_changed
        )
        self.style_combo.currentIndexChanged.connect(
            self._style_changed
        )

        return page

    def _build_response_page(self) -> QWidget:
        """Собирает страницу печати ответа и задержки."""

        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.typing_checkbox = QCheckBox(
            "Эмуляция печати ответа",
            page,
        )
        self.typing_checkbox.setToolTip(
            "Показывать ответ по символам, а не целиком"
        )

        self.typing_speed_combo = QComboBox(page)

        for speed, title in TYPING_SPEEDS:
            self.typing_speed_combo.addItem(title, speed)

        speed = int(
            self.response_values["typing_speed"]
        )
        speed_index = self.typing_speed_combo.findData(speed)

        if speed_index < 0:
            speed_index = self.typing_speed_combo.findData(35)

        self.typing_speed_combo.setCurrentIndex(
            max(0, speed_index)
        )

        self.typing_instant_checkbox = QCheckBox(
            "Мгновенный ответ",
            page,
        )
        self.typing_instant_checkbox.setToolTip(
            "Отключить печать, даже если эмуляция включена"
        )

        self.delay_checkbox = QCheckBox("Задержка ответа", page)
        self.delay_checkbox.setToolTip(
            "Небольшая пауза перед показом готового ответа"
        )

        self.delay_input = QDoubleSpinBox(page)
        self.delay_input.setRange(0.0, 10.0)
        self.delay_input.setDecimals(1)
        self.delay_input.setSingleStep(0.5)
        self.delay_input.setSuffix(" с")
        self.delay_input.setValue(
            float(self.response_values["delay_seconds"])
        )

        self.typing_checkbox.setChecked(
            bool(self.response_values["typing_enabled"])
        )
        self.typing_instant_checkbox.setChecked(
            bool(self.response_values["typing_instant"])
        )
        self.delay_checkbox.setChecked(
            bool(self.response_values["delay_enabled"])
        )

        typing_hint = QLabel(
            "Скорость — сколько символов ответа появляется за секунду. "
            "«Мгновенный ответ» отключает печать, даже если эмуляция "
            "включена.",
            page,
        )
        typing_hint.setObjectName("dialogHint")
        typing_hint.setWordWrap(True)

        delay_hint = QLabel(
            "Задержка добавляет паузу перед показом уже готового ответа. "
            "Индикатор ожидания в это время остаётся на экране.",
            page,
        )
        delay_hint.setObjectName("dialogHint")
        delay_hint.setWordWrap(True)

        form = QFormLayout()
        form.setSpacing(8)
        form.addRow(self.typing_checkbox)
        form.addRow("Скорость печати:", self.typing_speed_combo)
        form.addRow(self.typing_instant_checkbox)
        form.addRow(typing_hint)
        form.addRow(self.delay_checkbox)
        form.addRow("Задержка:", self.delay_input)
        form.addRow(delay_hint)

        self._sync_response_controls()

        self.typing_checkbox.toggled.connect(
            self._sync_response_controls
        )
        self.typing_instant_checkbox.toggled.connect(
            self._sync_response_controls
        )
        self.delay_checkbox.toggled.connect(
            self._sync_response_controls
        )

        layout.addLayout(form)
        layout.addStretch(1)

        return page

    def _sync_response_controls(self) -> None:
        """Включает только доступные поля вывода ответа."""

        typing = self.typing_checkbox.isChecked()
        instant = self.typing_instant_checkbox.isChecked()

        self.typing_instant_checkbox.setEnabled(typing)
        self.typing_speed_combo.setEnabled(
            typing and not instant
        )
        self.delay_input.setEnabled(
            self.delay_checkbox.isChecked()
        )

    def _current_role(self) -> str:
        """Возвращает выбранную группу текста."""

        role = self.color_role_combo.currentData()

        return str(role) if role else "bot"

    def _load_role_controls(self) -> None:
        """Показывает цвет, размер и стиль выбранной группы."""

        role = self._current_role()

        style = self.styles.get(role, "normal")
        style_index = self.style_combo.findData(style)

        self.style_combo.blockSignals(True)
        self.style_combo.setCurrentIndex(max(0, style_index))
        self.style_combo.blockSignals(False)

        self.role_font_size_input.blockSignals(True)
        self.role_font_size_input.setValue(
            int(self.font_sizes.get(role, 0))
        )
        self.role_font_size_input.blockSignals(False)

        self._refresh_color_button()
        self._update_preview()

    def _font_family_changed(self, font: QFont) -> None:
        """Запоминает новую гарнитуру."""

        self.font_family = font.family()
        self._update_preview()

    def _font_size_changed(self, size: int) -> None:
        """Запоминает новый размер шрифта."""

        self.font_size = int(size)
        self._update_preview()

    def _role_changed(self, _index: int) -> None:
        """Переключает цвет и стиль на выбранную группу."""

        self._load_role_controls()

    def _style_changed(self, _index: int) -> None:
        """Запоминает стиль текущей группы."""

        style = self.style_combo.currentData()

        if style:
            self.styles[self._current_role()] = str(style)
            self._update_preview()

    def _role_font_size_changed(self, size: int) -> None:
        """Запоминает свой размер выбранной группы."""

        self.font_sizes[self._current_role()] = int(size)
        self._update_preview()

    def _role_font_size(self, role: str) -> int:
        """Размер предпросмотра: свой у группы или общий."""

        size = int(self.font_sizes.get(role, 0))

        return size if size > 0 else self.font_size

    def _refresh_color_button(self) -> None:
        """Показывает цвет текущей группы на кнопке."""

        color = self.colors.get(self._current_role(), "#7cf58f")
        qcolor = QColor(color)

        brightness = (
            qcolor.red() * 299
            + qcolor.green() * 587
            + qcolor.blue() * 114
        ) / 1000

        text_color = "#000000" if brightness > 150 else "#ffffff"

        self.color_swatch_button.setText(color.upper())
        self.color_swatch_button.setStyleSheet(
            "border-image: none;"
            " border: 1px solid #3a2e25;"
            " border-radius: 3px;"
            f" background-color: {color};"
            f" color: {text_color};"
        )

    def _pick_color(self) -> None:
        """Открывает палитру для текущей группы текста."""

        role = self._current_role()
        current = QColor(self.colors.get(role, "#7cf58f"))

        color = QColorDialog.getColor(
            current,
            self,
            "Цвет шрифта",
        )

        if not color.isValid():
            return

        self.colors[role] = color.name()

        self._refresh_color_button()
        self._update_preview()

    def _update_preview(self) -> None:
        """Показывает образец выбранного шрифта и цвета."""

        role = self._current_role()
        style = self.styles.get(role, "normal")
        color = self.colors.get(role, "#7cf58f")

        font = QFont(self.font_family)
        font.setPointSize(self._role_font_size(role))
        font.setBold(style in ("bold", "bold_italic"))
        font.setItalic(style in ("italic", "bold_italic"))

        self.preview_label.setFont(font)
        self.preview_label.setStyleSheet(
            "background-color:#05100a;"
            " border:1px solid #23421f;"
            " border-radius:4px;"
            " padding:12px;"
            f" color:{color};"
        )

    def settings_payload(
        self,
    ) -> tuple[
        str,
        int,
        dict[str, str],
        dict[str, str],
        dict,
        dict[str, int],
    ]:
        """Возвращает все настройки страницы «Вид»."""

        response = {
            "typing_enabled": self.typing_checkbox.isChecked(),
            "typing_instant": (
                self.typing_instant_checkbox.isChecked()
            ),
            "typing_speed": int(
                self.typing_speed_combo.currentData()
                or DEFAULT_RESPONSE_SETTINGS["typing_speed"]
            ),
            "delay_enabled": self.delay_checkbox.isChecked(),
            "delay_seconds": round(
                float(self.delay_input.value()),
                1,
            ),
        }

        return (
            self.font_family_combo.currentFont().family(),
            int(self.font_size_input.value()),
            dict(self.colors),
            dict(self.styles),
            response,
            dict(self.font_sizes),
        )
