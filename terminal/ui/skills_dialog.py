# Giperion/app/ui/skills_dialog.py                                  v004
# Окно «Умения»: навыки агента и возможности активной модели ИИ.
# Последнее изменение: крупные подписи закладок.

from PySide6.QtWidgets import (
    QDialogButtonBox,
    QLabel,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from giperion.identity_matrix import IDENTITY_MATRIX
from terminal.core.model_registry import DEFAULT_MODEL_ID, get_active_model
from terminal.ui.dialog_text import build_skills_html
from terminal.ui.dialogs_base import SkinDialog, show_tool_window
from terminal.ui.tab_strip import TabStrip
from terminal.ui.value_text import model_skill_entries


def _build_skills_page(
    parent,
    skills: list[dict],
    hint: str,
) -> QWidget:
    """Собирает страницу закладки: подсказка и экран умений в рамке."""

    page = QWidget(parent)

    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    hint_label = QLabel(hint, page)
    hint_label.setObjectName("dialogHint")
    hint_label.setWordWrap(True)

    frame = QWidget(page)
    frame.setObjectName("skillsScreenFrame")

    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(6, 6, 6, 6)
    frame_layout.setSpacing(0)

    view = QTextBrowser(frame)
    view.setObjectName("skillsView")
    view.setOpenLinks(False)
    view.setHtml(build_skills_html(skills))

    frame_layout.addWidget(view)

    layout.addWidget(hint_label)
    layout.addWidget(frame, 1)

    return page


def show_skills_dialog(parent) -> None:
    """Открывает окно «Умения» с двумя разделами.

    «Навыки агента» — постоянный набор исполнительного ядра.
    «Умения ИИ» — возможности активной модели из её карточки.
    """

    executive_skills = IDENTITY_MATRIX["skills"]
    model = get_active_model()

    dialog = SkinDialog(
        parent,
        "Умения",
        min_width=640,
        min_height=520,
    )

    layout = dialog.body_layout

    title = QLabel("УМЕНИЯ", dialog)
    title.setObjectName("dialogTitle")

    subtitle = QLabel(
        "Закладка «Навыки агента» — постоянные навыки исполнительного "
        "ядра, закладка «Умения ИИ» — возможности выбранной модели.",
        dialog,
    )
    subtitle.setObjectName("dialogHint")
    subtitle.setWordWrap(True)

    tabs = QTabWidget(dialog)
    tabs.setObjectName("skillsTabs")
    tabs.setDocumentMode(True)
    tabs.tabBar().hide()

    executive_hint = (
        f"Исполнительное ядро: {len(executive_skills)} навыков. "
        "Этот набор не зависит от выбранной модели."
    )

    if model is not None:
        model_name = model["name"]
        provider = model.get("provider") or "источник не указан"
        model_hint = (
            f"Активное ядро ИИ: {model_name} · {provider}. "
            "Умения взяты из карточки модели."
        )
        model_skills = model_skill_entries(model)
    else:
        model_hint = "Активная модель не выбрана."
        model_skills = [
            {
                "name": "Модель не выбрана",
                "description": "Выбери модель в окне «Модель».",
            }
        ]

    tabs.addTab(
        _build_skills_page(
            tabs,
            executive_skills,
            executive_hint,
        ),
        "Навыки агента",
    )
    tabs.addTab(
        _build_skills_page(
            tabs,
            model_skills,
            model_hint,
        ),
        "Умения ИИ",
    )

    strip = TabStrip(tabs, ("Навыки агента", "Умения ИИ"))
    strip.setObjectName("skillsTabStrip")
    strip.tab_selected.connect(tabs.setCurrentIndex)

    # Для внешней модели сразу открываем её умения; у Гипериона
    # по умолчанию показываем постоянные навыки агента.
    initial_index = 0

    if model is not None and model["id"] != DEFAULT_MODEL_ID:
        initial_index = 1

    tabs.setCurrentIndex(initial_index)
    strip.set_current_index(initial_index)

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addWidget(strip)
    layout.addWidget(tabs, 1)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok, dialog)
    buttons.button(QDialogButtonBox.Ok).setText("Закрыть")
    buttons.accepted.connect(dialog.accept)

    layout.addWidget(buttons)

    show_tool_window(parent, dialog, "skills")
