# Giperion/terminal/ui/model_params_dialog.py                        v001
# Окно «Параметры ИИ»: паспорт модели и её известные характеристики.
# Последнее изменение: первый вариант — разделы паспорта и карточка модели.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialogButtonBox,
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
from terminal.ui.dialogs_base import SkinDialog
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
    """Добавляет раздел: заголовок и таблицу «параметр — значение»."""

    caption = QLabel(title, parent)
    caption.setObjectName("settingsSection")

    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(5)
    grid.setColumnStretch(1, 1)

    for row_index, (name, value) in enumerate(rows):
        name_label = QLabel(f"{name}:", parent)
        name_label.setObjectName("systemName")
        name_label.setWordWrap(True)

        value_label = QLabel(str(value), parent)
        value_label.setObjectName("systemValue")
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        grid.addWidget(name_label, row_index, 0)
        grid.addWidget(value_label, row_index, 1)

    layout.addWidget(caption)
    layout.addLayout(grid)


def build_params_content(parent: QWidget, model: dict) -> QWidget:
    """Собирает прокручиваемое содержимое окна «Параметры ИИ»."""

    content = QWidget(parent)
    content.setObjectName("systemContent")

    layout = QVBoxLayout(content)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)

    passport = get_passport(model["id"])

    if passport is not None:
        for title, rows in passport_sections(passport):
            _add_section(layout, content, title, rows)

        notes = passport_notes(passport)

        if notes:
            caption = QLabel("ЗАМЕТКИ", content)
            caption.setObjectName("settingsSection")
            layout.addWidget(caption)

            for note in notes:
                label = QLabel("• " + note, content)
                label.setObjectName("dialogHint")
                label.setWordWrap(True)
                layout.addWidget(label)
    else:
        for title, rows in _catalog_sections(model):
            _add_section(layout, content, title, rows)

        hint = QLabel(
            "Паспорт этой модели пока не заполнен. "
            "Известные данные взяты из каталога моделей.",
            content,
        )
        hint.setObjectName("dialogHint")
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

    dialog.exec()
