# Giperion/terminal/ui/window_help.py                               v001
# Заглушка раздела справки для кнопки «?» в планке окна.
# Последнее изменение: общая точка для будущей справки по окнам.

from PySide6.QtWidgets import QMessageBox


def show_window_help(parent, title: str) -> None:
    """Показывает, что раздел справки для окна ещё готовится."""

    QMessageBox.information(
        parent,
        "Справка",
        f"Раздел справки по окну «{title}» появится позже.",
    )
