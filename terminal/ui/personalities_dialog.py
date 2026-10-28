# Giperion/app/ui/personalities_dialog.py                           v002
# Окно «Личностные матрицы»: каталог и карточка характера.
# Последнее изменение: равные по высоте экраны в металлических рамках.

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from kraper_model.personality_catalog import (
    get_selected_personality_id,
    load_personality_matrices,
    set_selected_personality_id,
)
from terminal.ui.dialogs_base import SkinDialog, show_tool_window
from terminal.ui.rating_bars import fill_rating_bars


def _build_list(dialog) -> tuple[QVBoxLayout, QListWidget]:
    """Левая колонка: каталог матриц."""

    left = QVBoxLayout()
    left.setSpacing(6)

    caption = QLabel("КАТАЛОГ МАТРИЦ", dialog)
    caption.setObjectName("infoCaption")

    frame = QWidget(dialog)
    frame.setObjectName("personalityScreenFrame")

    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(6, 6, 6, 6)
    frame_layout.setSpacing(0)

    view = QListWidget(dialog)
    view.setObjectName("modelsView")
    view.setSelectionMode(QListWidget.SingleSelection)
    view.setMinimumWidth(250)

    frame_layout.addWidget(view)
    left.addWidget(caption)
    left.addWidget(frame, 1)

    return left, view


def _build_card(dialog) -> tuple:
    """Правая колонка: карточка личности."""

    right = QVBoxLayout()
    right.setSpacing(6)

    caption = QLabel("КАРТОЧКА ЛИЧНОСТИ", dialog)
    caption.setObjectName("infoCaption")

    frame = QWidget(dialog)
    frame.setObjectName("personalityScreenFrame")

    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(6, 6, 6, 6)
    frame_layout.setSpacing(0)

    scroll = QScrollArea(dialog)
    scroll.setObjectName("cardScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    card = QWidget()
    card.setObjectName("modelCard")

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(16, 14, 16, 14)
    card_layout.setSpacing(10)

    labels = {
        "name": QLabel(card),
        "role": QLabel(card),
        "motto": QLabel(card),
        "description": QLabel(card),
        "speech": QLabel(card),
        "strengths": QLabel(card),
        "risks": QLabel(card),
        "status": QLabel(card),
        "avatar": QLabel(card),
    }

    labels["name"].setObjectName("modelName")
    labels["name"].setWordWrap(True)
    labels["role"].setObjectName("modelProvider")
    labels["motto"].setObjectName("personalityMotto")
    labels["motto"].setWordWrap(True)
    for key in ("description", "speech", "strengths", "risks"):
        labels[key].setObjectName("modelDescription")
        labels[key].setWordWrap(True)
    labels["description"].setAlignment(Qt.AlignTop | Qt.AlignLeft)
    labels["status"].setObjectName("modelStatus")
    labels["status"].setWordWrap(True)
    labels["avatar"].setObjectName("modelAvatar")
    labels["avatar"].setFixedSize(96, 96)
    labels["avatar"].setAlignment(Qt.AlignCenter)

    traits_widget = QWidget(card)
    traits_layout = QVBoxLayout(traits_widget)
    traits_layout.setContentsMargins(0, 0, 0, 0)
    traits_layout.setSpacing(3)

    identity = QHBoxLayout()
    identity.setSpacing(12)
    identity.addWidget(labels["avatar"])
    identity.addWidget(traits_widget, 1)

    traits_caption = QLabel("ХАРАКТЕР · ОЦЕНКА 0–5", card)
    traits_caption.setObjectName("infoCaption")
    speech_caption = QLabel("МАНЕРА ОБЩЕНИЯ", card)
    speech_caption.setObjectName("infoCaption")
    strengths_caption = QLabel("СИЛЬНЫЕ СТОРОНЫ", card)
    strengths_caption.setObjectName("infoCaption")
    risks_caption = QLabel("РИСКИ", card)
    risks_caption.setObjectName("infoCaption")

    card_layout.addWidget(labels["name"])
    card_layout.addWidget(labels["role"])
    card_layout.addWidget(labels["motto"])
    card_layout.addWidget(traits_caption)
    card_layout.addLayout(identity)
    card_layout.addWidget(labels["description"])
    card_layout.addWidget(speech_caption)
    card_layout.addWidget(labels["speech"])
    card_layout.addWidget(strengths_caption)
    card_layout.addWidget(labels["strengths"])
    card_layout.addWidget(risks_caption)
    card_layout.addWidget(labels["risks"])
    card_layout.addStretch(1)
    card_layout.addWidget(labels["status"])

    scroll.setWidget(card)
    frame_layout.addWidget(scroll)
    right.addWidget(caption)
    right.addWidget(frame, 1)

    return right, labels, traits_layout, traits_widget


def _selected_matrix(view: QListWidget, matrices: list[dict]) -> dict | None:
    """Матрица, выбранная в списке."""

    item = view.currentItem()

    if item is None:
        return None

    matrix_id = item.data(Qt.UserRole)

    return next(
        (matrix for matrix in matrices if matrix["id"] == matrix_id),
        None,
    )


def _fill_traits(layout, widget, matrix: dict | None) -> None:
    """Шкалы характера выбранной матрицы."""

    ratings = (matrix.get("traits") or {}) if matrix else {}

    fill_rating_bars(
        layout,
        widget,
        ratings,
        name_width=92,
        empty_text="Черты не указаны",
    )


def _show_card(
    view: QListWidget,
    matrices: list[dict],
    selected: str,
    labels: dict,
    traits_layout,
    traits_widget,
    remember_button,
) -> None:
    """Заполняет карточку выбранной личности."""

    matrix = _selected_matrix(view, matrices)
    remember_button.setEnabled(False)

    if matrix is None:
        labels["name"].setText("Выбери матрицу")

        for key in (
            "role",
            "motto",
            "description",
            "speech",
            "strengths",
            "risks",
            "status",
            "avatar",
        ):
            labels[key].setText("")

        _fill_traits(traits_layout, traits_widget, None)

        return

    labels["name"].setText(matrix["name"])
    labels["role"].setText(matrix["role"])
    labels["motto"].setText(f"«{matrix['motto']}»")
    labels["description"].setText(matrix["description"])
    labels["speech"].setText(matrix["speech"])
    labels["strengths"].setText(matrix["strengths"])
    labels["risks"].setText(matrix["risks"])
    labels["avatar"].setText(matrix["symbol"])
    _fill_traits(traits_layout, traits_widget, matrix)

    is_selected = matrix["id"] == selected
    labels["status"].setText(
        f"Статус: {matrix['status']}. Влияние на ответы пока "
        "не подключено."
    )
    remember_button.setText(
        "Выбрана" if is_selected else "Запомнить выбор"
    )
    remember_button.setEnabled(not is_selected)


def _refresh_list(
    view: QListWidget,
    matrices: list[dict],
    selected: str,
    keep_id: str | None = None,
) -> None:
    """Перерисовывает каталог и сохраняет выбранную строку."""

    view.blockSignals(True)
    view.clear()

    for matrix in matrices:
        item = QListWidgetItem(
            f"{matrix['symbol']}  {matrix['name']}\n{matrix['role']}",
            view,
        )
        item.setData(Qt.UserRole, matrix["id"])

        font = item.font()
        is_selected = matrix["id"] == selected
        font.setBold(is_selected)
        item.setFont(font)
        item.setForeground(
            QColor("#7cf58f" if is_selected else "#cfe8d2")
        )

    target_id = keep_id or selected
    row = 0

    for index in range(view.count()):
        if view.item(index).data(Qt.UserRole) == target_id:
            row = index

            break

    if view.count():
        view.setCurrentRow(row)

    view.blockSignals(False)


def show_personalities_dialog(parent, on_select=None) -> None:
    """Открывает каталог личностных матриц: список и карточка личности."""

    matrices = load_personality_matrices()

    if not matrices:
        QMessageBox.warning(
            parent,
            "Личностные матрицы",
            "Каталог матриц не найден: data/personality_matrices.json.",
        )

        return

    selected = get_selected_personality_id()

    dialog = SkinDialog(
        parent,
        "Личностные матрицы",
        min_width=920,
        min_height=700,
    )

    title = QLabel("ЛИЧНОСТНЫЕ МАТРИЦЫ", dialog)
    title.setObjectName("dialogTitle")

    subtitle = QLabel(
        "Будущие модели поведения Гипериона: хакер, военный, писатель, "
        "мудрец, гопник и дипломат. Слева — каталог, справа — карточка "
        "личности. Выбор сохраняется, но пока не влияет на ответы.",
        dialog,
    )
    subtitle.setObjectName("dialogHint")
    subtitle.setWordWrap(True)

    left, view = _build_list(dialog)
    right, labels, traits_layout, traits_widget = _build_card(dialog)

    body = QHBoxLayout()
    body.setSpacing(12)
    body.addLayout(left, 1)
    body.addLayout(right, 2)

    remember_button = QPushButton("Запомнить выбор", dialog)
    remember_button.setObjectName("activateButton")
    remember_button.setCursor(Qt.ArrowCursor)
    remember_button.setMinimumHeight(38)
    remember_button.setMinimumWidth(180)

    close_box = QDialogButtonBox(QDialogButtonBox.Ok, dialog)
    close_box.button(QDialogButtonBox.Ok).setText("Закрыть")
    close_box.accepted.connect(dialog.accept)

    buttons_row = QHBoxLayout()
    buttons_row.setSpacing(8)
    buttons_row.addWidget(remember_button)
    buttons_row.addStretch(1)
    buttons_row.addWidget(close_box)

    def remember() -> None:
        """Сохраняет выбранную матрицу для будущего режима."""

        matrix = _selected_matrix(view, matrices)

        if matrix is None:
            return

        if not set_selected_personality_id(matrix["id"]):
            QMessageBox.warning(
                dialog,
                "Личностные матрицы",
                "Не удалось сохранить выбор матрицы.",
            )

            return

        _refresh_list(view, matrices, matrix["id"], matrix["id"])
        _show_card(
            view,
            matrices,
            matrix["id"],
            labels,
            traits_layout,
            traits_widget,
            remember_button,
        )

        if on_select is not None:
            on_select(matrix)

    view.currentItemChanged.connect(
        lambda current, previous: _show_card(
            view,
            matrices,
            selected,
            labels,
            traits_layout,
            traits_widget,
            remember_button,
        )
    )
    remember_button.clicked.connect(remember)

    dialog.body_layout.addWidget(title)
    dialog.body_layout.addWidget(subtitle)
    dialog.body_layout.addLayout(body, 1)
    dialog.body_layout.addLayout(buttons_row)

    _refresh_list(view, matrices, selected)
    _show_card(
        view,
        matrices,
        selected,
        labels,
        traits_layout,
        traits_widget,
        remember_button,
    )

    show_tool_window(parent, dialog, "personalities")
