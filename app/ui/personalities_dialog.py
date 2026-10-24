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
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.personality_catalog import (
    get_selected_personality_id,
    load_personality_matrices,
    set_selected_personality_id,
)
from app.ui.dialogs_base import SkinDialog


def show_personalities_dialog(parent, on_select=None) -> None:
    """Открывает каталог личностных матриц: список и карточка личности.

    Матрицы — будущие модели поведения ИИ. Выбор сохраняется, но пока
    не меняет ответы Гипериона: это задел для следующего этапа.
    """

    matrices = load_personality_matrices()

    if not matrices:
        QMessageBox.warning(
            parent,
            "Личностные матрицы",
            "Каталог матриц не найден: data/personality_matrices.json.",
        )

        return

    state = {
        "matrices": matrices,
        "selected": get_selected_personality_id(),
    }

    dialog = SkinDialog(
        parent,
        "Личностные матрицы",
        min_width=920,
        min_height=700,
    )

    layout = dialog.body_layout

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

    body = QHBoxLayout()
    body.setSpacing(12)

    # --- Левая колонка: список матриц ---
    left = QVBoxLayout()
    left.setSpacing(6)

    left_caption = QLabel("КАТАЛОГ МАТРИЦ", dialog)
    left_caption.setObjectName("infoCaption")

    left_frame = QWidget(dialog)
    left_frame.setObjectName("personalityScreenFrame")

    left_frame_layout = QVBoxLayout(left_frame)
    left_frame_layout.setContentsMargins(6, 6, 6, 6)
    left_frame_layout.setSpacing(0)

    view = QListWidget(dialog)
    view.setObjectName("modelsView")
    view.setSelectionMode(QListWidget.SingleSelection)
    view.setMinimumWidth(250)

    left_frame_layout.addWidget(view)
    left.addWidget(left_caption)
    left.addWidget(left_frame, 1)

    # --- Правая колонка: карточка личности ---
    right = QVBoxLayout()
    right.setSpacing(6)

    right_caption = QLabel("КАРТОЧКА ЛИЧНОСТИ", dialog)
    right_caption.setObjectName("infoCaption")

    right_frame = QWidget(dialog)
    right_frame.setObjectName("personalityScreenFrame")

    right_frame_layout = QVBoxLayout(right_frame)
    right_frame_layout.setContentsMargins(6, 6, 6, 6)
    right_frame_layout.setSpacing(0)

    scroll = QScrollArea(dialog)
    scroll.setObjectName("cardScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)

    card = QWidget()
    card.setObjectName("modelCard")

    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(16, 14, 16, 14)
    card_layout.setSpacing(10)

    name_label = QLabel(card)
    name_label.setObjectName("modelName")
    name_label.setWordWrap(True)

    role_label = QLabel(card)
    role_label.setObjectName("modelProvider")

    identity = QHBoxLayout()
    identity.setSpacing(12)

    avatar_label = QLabel(card)
    avatar_label.setObjectName("modelAvatar")
    avatar_label.setFixedSize(96, 96)
    avatar_label.setAlignment(Qt.AlignCenter)

    traits_widget = QWidget(card)
    traits_layout = QVBoxLayout(traits_widget)
    traits_layout.setContentsMargins(0, 0, 0, 0)
    traits_layout.setSpacing(3)

    identity.addWidget(avatar_label)
    identity.addWidget(traits_widget, 1)

    motto_label = QLabel(card)
    motto_label.setObjectName("personalityMotto")
    motto_label.setWordWrap(True)

    description_label = QLabel(card)
    description_label.setObjectName("modelDescription")
    description_label.setWordWrap(True)
    description_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

    traits_caption = QLabel("ХАРАКТЕР · ОЦЕНКА 0–5", card)
    traits_caption.setObjectName("infoCaption")

    speech_caption = QLabel("МАНЕРА ОБЩЕНИЯ", card)
    speech_caption.setObjectName("infoCaption")

    speech_label = QLabel(card)
    speech_label.setObjectName("modelDescription")
    speech_label.setWordWrap(True)

    strengths_caption = QLabel("СИЛЬНЫЕ СТОРОНЫ", card)
    strengths_caption.setObjectName("infoCaption")

    strengths_label = QLabel(card)
    strengths_label.setObjectName("modelDescription")
    strengths_label.setWordWrap(True)

    risks_caption = QLabel("РИСКИ", card)
    risks_caption.setObjectName("infoCaption")

    risks_label = QLabel(card)
    risks_label.setObjectName("modelDescription")
    risks_label.setWordWrap(True)

    status_label = QLabel(card)
    status_label.setObjectName("modelStatus")
    status_label.setWordWrap(True)

    card_layout.addWidget(name_label)
    card_layout.addWidget(role_label)
    card_layout.addWidget(motto_label)
    card_layout.addWidget(traits_caption)
    card_layout.addLayout(identity)
    card_layout.addWidget(description_label)
    card_layout.addWidget(speech_caption)
    card_layout.addWidget(speech_label)
    card_layout.addWidget(strengths_caption)
    card_layout.addWidget(strengths_label)
    card_layout.addWidget(risks_caption)
    card_layout.addWidget(risks_label)
    card_layout.addStretch(1)
    card_layout.addWidget(status_label)

    scroll.setWidget(card)

    right_frame_layout.addWidget(scroll)
    right.addWidget(right_caption)
    right.addWidget(right_frame, 1)

    body.addLayout(left, 1)
    body.addLayout(right, 2)

    # --- Кнопки окна ---
    buttons_row = QHBoxLayout()
    buttons_row.setSpacing(8)

    remember_button = QPushButton("Запомнить выбор", dialog)
    remember_button.setObjectName("activateButton")
    remember_button.setCursor(Qt.ArrowCursor)
    remember_button.setMinimumHeight(38)
    remember_button.setMinimumWidth(180)

    close_box = QDialogButtonBox(QDialogButtonBox.Ok, dialog)
    close_box.button(QDialogButtonBox.Ok).setText("Закрыть")
    close_box.accepted.connect(dialog.accept)

    buttons_row.addWidget(remember_button)
    buttons_row.addStretch(1)
    buttons_row.addWidget(close_box)

    def selected_matrix() -> dict | None:
        """Матрица, выбранная в левом списке."""

        item = view.currentItem()

        if item is None:
            return None

        matrix_id = item.data(Qt.UserRole)

        return next(
            (
                matrix
                for matrix in state["matrices"]
                if matrix["id"] == matrix_id
            ),
            None,
        )

    def fill_traits(matrix: dict | None) -> None:
        """Перерисовывает шкалы характера выбранной матрицы."""

        while traits_layout.count():
            item = traits_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        if matrix is None:
            return

        traits = matrix.get("traits") or {}

        if not traits:
            empty = QLabel("Черты не указаны", traits_widget)
            empty.setObjectName("strengthName")
            traits_layout.addWidget(empty)

            return

        for trait_name, value in traits.items():
            row = QWidget(traits_widget)

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            name = QLabel(trait_name, row)
            name.setObjectName("strengthName")
            name.setFixedWidth(92)

            bar = QProgressBar(row)
            bar.setObjectName("strengthBar")
            bar.setRange(0, 5)
            bar.setValue(value)
            bar.setTextVisible(False)
            bar.setFixedHeight(10)

            score = QLabel(str(value), row)
            score.setObjectName("strengthValue")
            score.setFixedWidth(14)

            row_layout.addWidget(name)
            row_layout.addWidget(bar, 1)
            row_layout.addWidget(score)
            traits_layout.addWidget(row)

    def show_card() -> None:
        """Заполняет карточку выбранной личности."""

        matrix = selected_matrix()
        remember_button.setEnabled(False)

        if matrix is None:
            name_label.setText("Выбери матрицу")
            role_label.setText("")
            motto_label.setText("")
            description_label.setText("")
            speech_label.setText("")
            strengths_label.setText("")
            risks_label.setText("")
            status_label.setText("")
            avatar_label.setText("")
            fill_traits(None)

            return

        name_label.setText(matrix["name"])
        role_label.setText(matrix["role"])
        motto_label.setText(f"«{matrix['motto']}»")
        description_label.setText(matrix["description"])
        speech_label.setText(matrix["speech"])
        strengths_label.setText(matrix["strengths"])
        risks_label.setText(matrix["risks"])
        avatar_label.setText(matrix["symbol"])
        fill_traits(matrix)

        is_selected = matrix["id"] == state["selected"]

        status_label.setText(
            f"Статус: {matrix['status']}. Влияние на ответы пока "
            "не подключено."
        )

        remember_button.setText(
            "Выбрана" if is_selected else "Запомнить выбор"
        )
        remember_button.setEnabled(not is_selected)

    def refresh_list(keep_id: str | None = None) -> None:
        """Перерисовывает каталог и сохраняет выбранную строку."""

        view.blockSignals(True)
        view.clear()

        for matrix in state["matrices"]:
            item = QListWidgetItem(
                f"{matrix['symbol']}  {matrix['name']}\n"
                f"{matrix['role']}",
                view,
            )
            item.setData(Qt.UserRole, matrix["id"])

            font = item.font()
            is_selected = matrix["id"] == state["selected"]
            font.setBold(is_selected)
            item.setFont(font)

            if is_selected:
                item.setForeground(QColor("#7cf58f"))
            else:
                item.setForeground(QColor("#cfe8d2"))

        target_id = keep_id or state["selected"]
        row = 0

        for index in range(view.count()):
            if view.item(index).data(Qt.UserRole) == target_id:
                row = index

                break

        if view.count():
            view.setCurrentRow(row)

        view.blockSignals(False)

        show_card()

    def remember() -> None:
        """Сохраняет выбранную матрицу для будущего режима."""

        matrix = selected_matrix()

        if matrix is None:
            return

        if not set_selected_personality_id(matrix["id"]):
            QMessageBox.warning(
                dialog,
                "Личностные матрицы",
                "Не удалось сохранить выбор матрицы.",
            )

            return

        state["selected"] = matrix["id"]
        refresh_list(matrix["id"])

        if on_select is not None:
            on_select(matrix)

    view.currentItemChanged.connect(
        lambda current, previous: show_card()
    )
    remember_button.clicked.connect(remember)

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addLayout(body, 1)
    layout.addLayout(buttons_row)

    refresh_list()
    dialog.exec()
