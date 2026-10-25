# Giperion/terminal/ui/model_params_dialog.py                        v001
# Окно «Параметры ИИ»: паспорт модели и её известные характеристики.
# Последнее изменение: первый вариант — разделы паспорта и карточка модели.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from terminal.core.model_passport import (
    UNKNOWN,
    get_passport,
    passport_notes,
    passport_sections,
)
from terminal.core.model_registry import (
    build_stars,
    get_reputation,
)
from terminal.ui.dialogs_base import SkinDialog, show_tool_window
from terminal.ui.value_text import (
    format_tokens,
    model_modalities_text,
    tokens_word,
)


def _catalog_sections(model: dict) -> list[tuple[str, list[tuple[str, str]]]]:
    """Разделы для модели без паспорта: всё, что есть в каталоге."""

    reputation = get_reputation(model["id"])

    context = model.get("context_limit") or 0
    context_text = (
        f"{format_tokens(context)} {tokens_word(context)}"
        if context
        else "не указан"
    )

    strengths = " · ".join(
        f"{name} {value}"
        for name, value in (model.get("strengths") or {}).items()
        if value > 0
    )

    capabilities = model.get("capabilities") or {}
    flags = []

    if capabilities.get("reasoning"):
        flags.append("рассуждения")

    if capabilities.get("tool_call"):
        flags.append("инструменты")

    if capabilities.get("structured_output"):
        flags.append("структурированный вывод")

    if capabilities.get("attachment"):
        flags.append("вложения")

    return [
        (
            "КАРТОЧКА",
            [
                ("Провайдер", model.get("provider") or UNKNOWN),
                ("Идентификатор", model.get("id") or UNKNOWN),
                ("Доступ", model.get("price") or UNKNOWN),
                ("Контекст", context_text),
                ("Вход и выход", model_modalities_text(model)),
                (
                    "Функции",
                    ", ".join(flags) if flags else "не указаны",
                ),
                (
                    "Сильные стороны",
                    strengths if strengths else "не указаны",
                ),
                (
                    "Репутация",
                    f"{reputation['requests']} обращений · "
                    f"{build_stars(reputation['stars'])}",
                ),
            ],
        ),
    ]


def _add_section(
    layout: QVBoxLayout,
    parent: QWidget,
    title: str,
    rows: list[tuple[str, str]],
) -> None:
    """Добавляет раздел: тонкая рамка и зелёный экран на всю её площадь."""

    plate = QFrame(parent)
    plate.setObjectName("paramsPlate")

    plate_layout = QVBoxLayout(plate)
    plate_layout.setContentsMargins(0, 0, 0, 0)
    plate_layout.setSpacing(0)

    screen = QWidget(plate)
    screen.setObjectName("paramsScreen")
    screen.setAttribute(Qt.WA_StyledBackground, True)

    grid = QGridLayout(screen)
    grid.setContentsMargins(12, 9, 12, 10)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(5)
    grid.setColumnStretch(1, 1)

    caption = QLabel(title, screen)
    caption.setObjectName("paramsPlateTitle")

    grid.addWidget(caption, 0, 0, 1, 2)

    for row_index, (name, value) in enumerate(rows, start=1):
        name_label = QLabel(f"{name}:", screen)
        name_label.setObjectName("paramsKey")
        name_label.setWordWrap(True)

        value_label = QLabel(str(value), screen)
        value_label.setObjectName("paramsValue")
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        grid.addWidget(name_label, row_index, 0)
        grid.addWidget(value_label, row_index, 1)

    plate_layout.addWidget(screen)

    layout.addWidget(plate)


def _add_notes(
    layout: QVBoxLayout,
    parent: QWidget,
    notes: list[str],
) -> None:
    """Добавляет рамку с заметками на зелёном экране."""

    plate = QFrame(parent)
    plate.setObjectName("paramsPlate")

    plate_layout = QVBoxLayout(plate)
    plate_layout.setContentsMargins(0, 0, 0, 0)
    plate_layout.setSpacing(0)

    screen = QWidget(plate)
    screen.setObjectName("paramsScreen")
    screen.setAttribute(Qt.WA_StyledBackground, True)

    screen_layout = QVBoxLayout(screen)
    screen_layout.setContentsMargins(12, 9, 12, 10)
    screen_layout.setSpacing(5)

    caption = QLabel("ЗАМЕТКИ", screen)
    caption.setObjectName("paramsPlateTitle")
    screen_layout.addWidget(caption)

    for note in notes:
        label = QLabel("• " + note, screen)
        label.setObjectName("paramsNote")
        label.setWordWrap(True)
        screen_layout.addWidget(label)

    plate_layout.addWidget(screen)

    layout.addWidget(plate)


def build_params_content(parent: QWidget, model: dict) -> QWidget:
    """Собирает прокручиваемое содержимое окна «Параметры ИИ»."""

    content = QWidget(parent)
    content.setObjectName("paramsContent")

    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 6, 0)
    layout.setSpacing(12)

    passport = get_passport(model["id"])

    if passport is not None:
        for title, rows in passport_sections(passport):
            _add_section(layout, content, title, rows)

        notes = passport_notes(passport)

        if notes:
            _add_notes(layout, content, notes)
    else:
        for title, rows in _catalog_sections(model):
            _add_section(layout, content, title, rows)

        hint = QLabel(
            "Паспорт этой модели пока не заполнен. "
            "Известные данные взяты из каталога моделей.",
            content,
        )
        hint.setObjectName("paramsNote")
        hint.setWordWrap(True)
        layout.addWidget(hint)

    layout.addStretch(1)

    return content


def show_model_params_dialog(parent, model: dict) -> None:
    """Открывает окно «Параметры ИИ» для выбранной модели."""

    dialog = SkinDialog(
        parent,
        "Параметры ИИ",
        min_width=760,
        min_height=680,
    )

    title = QLabel("ПАРАМЕТРЫ ИИ", dialog)
    title.setObjectName("dialogTitle")

    subtitle = QLabel(
        f"{model.get('name', '')} · {model.get('provider', '')}",
        dialog,
    )
    subtitle.setObjectName("dialogHint")
    subtitle.setWordWrap(True)

    scroll = QScrollArea(dialog)
    scroll.setObjectName("systemScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(build_params_content(scroll, model))

    buttons = QDialogButtonBox(QDialogButtonBox.Close, dialog)
    buttons.button(QDialogButtonBox.Close).setText("Закрыть")
    buttons.rejected.connect(dialog.reject)

    dialog.body_layout.addWidget(title)
    dialog.body_layout.addWidget(subtitle)
    dialog.body_layout.addWidget(scroll, 1)
    dialog.body_layout.addWidget(buttons)

    show_tool_window(
        parent,
        dialog,
        "params:" + str(model.get("id", "")),
    )
