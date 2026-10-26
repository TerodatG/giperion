# Giperion/terminal/ui/window_chrome_mixin.py                       v006
# Безрамочное окно: каркас, планка заголовка, перетаскивание и ресайз.
# Последнее изменение: на планке только название «ГИПЕРИОН».

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from shared.action_log import add_action
from terminal.ui.dialogs_base import SkinDialog
from terminal.ui.theme import WINDOW_EDGE_MARGIN
from terminal.ui.window_events import WindowCursorFilter
from terminal.ui.window_help import show_window_help

# Ширина левой панели: запас под две закладки параметров.
LEFT_PANEL_WIDTH = 336


class WindowChromeMixin:
    """Методы окна, отвечающие только за рамку и планку заголовка."""

    def _build_window_shell(self) -> None:
        """Оборачивает окно в металлическую шкуру вместо рамки Windows."""

        window = self.window

        window.setWindowFlag(Qt.FramelessWindowHint, True)
        window.setAttribute(Qt.WA_StyledBackground, True)

        # Системное меню окна больше не нужно.
        window.menuBar().hide()

        # Статусбар заменяет подпись на планке заголовка.
        window.statusBar().hide()

        central = window.takeCentralWidget()

        if central is not None:
            central.setObjectName("centralwidget")
            central.setAttribute(Qt.WA_StyledBackground, True)

        shell = QWidget(window)
        shell.setObjectName("windowShell")
        shell.setAttribute(Qt.WA_StyledBackground, True)

        self.shell = shell
        self.title_bar = self._build_title_bar(shell)

        layout = QVBoxLayout(shell)
        layout.setContentsMargins(7, 7, 7, 7)
        layout.setSpacing(7)
        layout.addWidget(self.title_bar)

        if central is not None:
            layout.addWidget(central, 1)

        # Металлическая полоса под планкой заголовка.
        self.title_glow = QWidget(shell)
        self.title_glow.setObjectName("titleGlow")
        self.title_glow.setFixedHeight(2)
        self.title_glow.setAttribute(Qt.WA_StyledBackground, True)

        layout.insertWidget(1, self.title_glow)

        window.setCentralWidget(shell)

        # Левая колонка уже на одну кнопку модуля: терминал получает
        # освободившееся место, а параметры больше не выходят за окно.
        for panel in (window.avatarPanel, window.personalityPanel):
            panel.setMinimumWidth(LEFT_PANEL_WIDTH)
            panel.setMaximumWidth(LEFT_PANEL_WIDTH)

        # Правой панели нужна ширина для списка открытых чатов.
        window.toolsPanel.setMinimumWidth(198)
        window.toolsPanel.setMaximumWidth(198)
        window.setMinimumSize(1080, 760)

        # Тянется только терминал: боковые панели остаются узкими.
        central_layout = central.layout() if central is not None else None

        if central_layout is not None:
            central_layout.setColumnStretch(0, 0)
            central_layout.setColumnStretch(1, 1)
            central_layout.setColumnStretch(2, 0)

        # Тянем окно за шкуру: края — растягивание, планка — перенос.
        for chrome in (shell, self.title_bar):
            chrome.setMouseTracking(True)
            chrome.mousePressEvent = (
                lambda event, item=chrome: self._on_chrome_press(
                    item, event
                )
            )

        self.title_bar.mouseDoubleClickEvent = (
            lambda event: self._toggle_maximize()
        )

        # Закрытие окна — только после подтверждения.
        self.closing_confirmed = False

        # Курсор у краёв считаем по всему окну: иначе кнопки наследуют
        # «стрелку в обе стороны» у нижней кромки. Тот же фильтр
        # перехватывает закрытие окна.
        self.cursor_filter = WindowCursorFilter(self)
        application = QApplication.instance()

        if application is not None:
            application.installEventFilter(self.cursor_filter)

    def _confirm_window_close(self) -> bool:
        """Спрашивает подтверждение закрытия окна.

        Возвращает True, если окно можно закрывать.
        """

        if self.closing_confirmed:
            return True

        dialog = SkinDialog(
            self.window,
            "Завершение работы",
            min_width=480,
            min_height=210,
        )

        question = QLabel("Закрыть Терминал?", dialog)
        question.setObjectName("closeScreen")
        question.setAlignment(Qt.AlignCenter)
        question.setWordWrap(True)
        question.setMinimumHeight(74)

        plate = QWidget(dialog)
        plate.setObjectName("closePlate")
        plate.setAttribute(Qt.WA_StyledBackground, True)

        plate_layout = QVBoxLayout(plate)
        plate_layout.setContentsMargins(14, 14, 14, 14)
        plate_layout.addWidget(question)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            dialog,
        )
        buttons.button(QDialogButtonBox.Ok).setText("Закрыть")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        dialog.body_layout.addWidget(plate, 1)
        dialog.body_layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return False

        self.closing_confirmed = True
        add_action("Гиперион завершил работу (окно)")

        return True

    def _build_title_bar(self, parent) -> QWidget:
        """Собирает собственную планку заголовка с кнопками окна."""

        bar = QWidget(parent)
        bar.setObjectName("titleBar")
        bar.setFixedHeight(54)
        bar.setAttribute(Qt.WA_StyledBackground, True)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 2, 8, 2)
        layout.setSpacing(9)

        emblem = QLabel("◈", bar)
        emblem.setObjectName("titleBadge")
        layout.addWidget(emblem)

        title = QLabel("ГИПЕРИОН", bar)
        title.setObjectName("titleText")

        # Красное свечение букв, как у индикаторов станции.
        glow = QGraphicsDropShadowEffect(title)
        glow.setColor(QColor(255, 80, 40, 190))
        glow.setBlurRadius(16)
        glow.setOffset(0, 0)
        title.setGraphicsEffect(glow)

        layout.addWidget(title)

        layout.addStretch(1)

        help_button = self._make_title_button(
            bar, "?", "Справка по окну"
        )
        minimize_button = self._make_title_button(
            bar, "—", "Свернуть"
        )
        self.maximize_button = self._make_title_button(
            bar, "▢", "Развернуть"
        )
        close_button = self._make_title_button(
            bar, "✕", "Закрыть", closing=True
        )

        for button in (
            help_button,
            minimize_button,
            self.maximize_button,
            close_button,
        ):
            layout.addWidget(button)

        help_button.clicked.connect(self._request_window_help)
        minimize_button.clicked.connect(self.window.showMinimized)
        self.maximize_button.clicked.connect(self._toggle_maximize)
        close_button.clicked.connect(self.window.close)

        # Значки и подписи не мешают тянуть окно за планку.
        for element in (emblem, title):
            element.setAttribute(
                Qt.WA_TransparentForMouseEvents, True
            )

        return bar

    @staticmethod
    def _make_title_button(
        parent,
        text: str,
        tooltip: str,
        closing: bool = False,
    ) -> QPushButton:
        """Создаёт кнопку планки заголовка в стиле «Настройки»."""

        button = QPushButton(text, parent)
        button.setObjectName("closeButton" if closing else "titleButton")
        button.setToolTip(tooltip)
        button.setFixedSize(40, 30)
        button.setFocusPolicy(Qt.NoFocus)
        button.setCursor(Qt.ArrowCursor)

        return button

    def _request_window_help(self) -> None:
        """Открывает раздел справки по главному окну."""

        show_window_help(self.window, "Гиперион")

    def _toggle_maximize(self) -> None:
        """Разворачивает окно на весь экран и обратно."""

        if self.window.isMaximized():
            self.window.showNormal()

            geometry = getattr(self, "_normal_geometry", None)

            if geometry is not None:
                self.window.setGeometry(geometry)
                self._normal_geometry = None

            self.maximize_button.setText("▢")
            self.maximize_button.setToolTip("Развернуть")
        else:
            self._normal_geometry = self.window.geometry()
            self.window.showMaximized()
            self.maximize_button.setText("❐")
            self.maximize_button.setToolTip("Свернуть в окно")

    def _window_edges(self, point) -> Qt.Edges:
        """Определяет, за какой край окна цепляется курсор."""

        edges = Qt.Edges()

        width = self.window.width()
        height = self.window.height()

        if point.x() <= WINDOW_EDGE_MARGIN:
            edges |= Qt.LeftEdge
        elif point.x() >= width - WINDOW_EDGE_MARGIN:
            edges |= Qt.RightEdge

        if point.y() <= WINDOW_EDGE_MARGIN:
            edges |= Qt.TopEdge
        elif point.y() >= height - WINDOW_EDGE_MARGIN:
            edges |= Qt.BottomEdge

        return edges

    @staticmethod
    def _edge_cursor(edges) -> Qt.CursorShape:
        """Подбирает курсор под край окна."""

        left = bool(edges & Qt.LeftEdge)
        right = bool(edges & Qt.RightEdge)
        top = bool(edges & Qt.TopEdge)
        bottom = bool(edges & Qt.BottomEdge)

        if (left and top) or (right and bottom):
            return Qt.SizeFDiagCursor

        if (right and top) or (left and bottom):
            return Qt.SizeBDiagCursor

        if left or right:
            return Qt.SizeHorCursor

        if top or bottom:
            return Qt.SizeVerCursor

        return Qt.ArrowCursor

    def _on_chrome_press(self, widget, event) -> None:
        """Начинает перенос или растягивание окна."""

        if event.button() != Qt.LeftButton:
            event.ignore()

            return

        handle = self.window.windowHandle()

        position = widget.mapTo(
            self.window,
            event.position().toPoint(),
        )

        edges = self._window_edges(position)

        if edges:
            if handle is not None:
                handle.startSystemResize(edges)

            event.accept()

            return

        if widget is self.title_bar:
            if handle is not None:
                handle.startSystemMove()

            event.accept()

            return

        event.ignore()

    def center_on_screen(self) -> None:
        """Ставит окно в середину рабочего стола."""

        screen = QApplication.primaryScreen()

        if screen is None:
            return

        area = screen.availableGeometry()
        frame = self.window.frameGeometry()
        frame.moveCenter(area.center())

        self.window.move(frame.topLeft())
