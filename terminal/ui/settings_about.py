# Giperion/terminal/ui/settings_about.py                               v001
# Страница «О нас»: версия, платформа, команда и принципы.
# Последнее изменение: вынесено из settings_dialog.

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from terminal.core.app_version import (
    current_released,
    current_version,
)
from terminal.core.system_info import format_bytes, get_system_info
from terminal.ui.dialog_text import format_release_date


def _plate(
    parent,
    caption_text: str,
    rows: tuple[tuple[str, str], ...],
) -> QFrame:
    """Собирает плиту раздела с ровными строками."""

    frame = QFrame(parent)
    frame.setObjectName("paramsPlate")

    frame_layout = QVBoxLayout(frame)
    frame_layout.setContentsMargins(0, 0, 0, 0)
    frame_layout.setSpacing(0)

    screen = QWidget(frame)
    screen.setObjectName("paramsScreen")

    grid = QGridLayout(screen)
    grid.setContentsMargins(12, 9, 12, 10)
    grid.setHorizontalSpacing(14)
    grid.setVerticalSpacing(6)
    grid.setColumnStretch(1, 1)

    caption = QLabel(caption_text, screen)
    caption.setObjectName("paramsPlateTitle")
    grid.addWidget(caption, 0, 0, 1, 2)

    for index, (name, value) in enumerate(rows, start=1):
        key_label = QLabel(f"{name}:", screen)
        key_label.setObjectName("paramsKey")
        key_label.setWordWrap(True)

        value_label = QLabel(value, screen)
        value_label.setObjectName("paramsValue")
        value_label.setWordWrap(True)

        grid.addWidget(key_label, index, 0)
        grid.addWidget(value_label, index, 1)

    frame_layout.addWidget(screen)

    return frame


def _program_rows(info: dict, pyside_version: str) -> tuple:
    """Строки раздела «О программе»."""

    return (
        (
            "Версия",
            f"{current_version()} от "
            f"{format_release_date(current_released())}",
        ),
        (
            "Платформа",
            f"{info['os']} · Python {info['python']} · "
            f"PySide6 {pyside_version}",
        ),
        (
            "Компьютер",
            f"{info['processor']} · "
            f"{format_bytes(info['ram_total'])} ОЗУ",
        ),
        (
            "Нейросеть",
            f"PyTorch {info['torch']} · CUDA {info['cuda']}",
        ),
        ("Исходники", "локальный git-репозиторий проекта"),
    )


def _team_rows() -> tuple:
    """Строки раздела «Команда»."""

    return (
        (
            "Разработчик",
            "Terodat — автор проекта, интерфейса и модели.",
        ),
        (
            "ИИ-соавтор",
            "DeepSeek V4.1 Flash — код, тесты и архитектура.",
        ),
        (
            "Благодарности",
            "PySide6 (Qt), PyTorch, OpenCode — инструменты, "
            "на которых стоит терминал.",
        ),
    )


def _principle_rows() -> tuple:
    """Строки раздела «Принципы»."""

    return (
        (
            "Локальность",
            "Диалоги, память и файлы не уходят в облако без запроса.",
        ),
        (
            "Контроль",
            "Опасные действия агента ждут подтверждения человека.",
        ),
        (
            "Обновления",
            "Только по кнопке: проверка sha256, резервная копия "
            "и запись версии.",
        ),
        (
            "Прозрачность",
            "Журнал действий, паспорт модели и открытые данные проекта.",
        ),
    )


def _feedback_rows() -> tuple:
    """Строки раздела «Обратная связь»."""

    return (
        (
            "Журнал действий",
            "logs/actions.log — что делал терминал.",
        ),
        (
            "Данные",
            "data/ — каталог моделей, дроны, история и настройки.",
        ),
        (
            "Об ошибке",
            "Опиши шаги и приложи последние строки журнала: "
            "так причину видно сразу.",
        ),
    )


def build_about_page(parent) -> QWidget:
    """Собирает страницу «О нас»."""

    from PySide6 import __version__ as pyside_version

    info = get_system_info()

    page = QWidget(parent)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    title = QLabel("О ПРОЕКТЕ", page)
    title.setObjectName("dialogTitle")

    intro = QLabel(
        "Giperion — локальный ИИ-собеседник: собственная нейросетевая "
        "модель, агент «Терминал» и оконный интерфейс в духе "
        "терминала. Диалоги, память и файлы остаются на этом "
        "компьютере, а внешние модели подключаются по желанию.",
        page,
    )
    intro.setWordWrap(True)

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

    content_layout.addWidget(
        _plate(content, "О ПРОГРАММЕ", _program_rows(info, pyside_version))
    )
    content_layout.addWidget(_plate(content, "КОМАНДА", _team_rows()))
    content_layout.addWidget(_plate(content, "ПРИНЦИПЫ", _principle_rows()))
    content_layout.addWidget(
        _plate(content, "ОБРАТНАЯ СВЯЗЬ", _feedback_rows())
    )
    content_layout.addStretch(1)

    scroll.setWidget(content)

    layout.addWidget(title)
    layout.addWidget(intro)
    layout.addWidget(scroll, 1)

    return page
