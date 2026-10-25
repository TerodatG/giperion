# Giperion/terminal/ui/window_style.py                             v031
# Единая таблица стилей окна: тёмный металл, зелёные экраны и ржавые плиты.
# Последнее изменение: QSS вынесен в assets/ui/window.qss.

from config import BASE_DIR

UI_DIR = BASE_DIR / "assets" / "ui"

STYLE_FILE = UI_DIR / "window.qss"

# Подстановки в QSS: плейсхолдер → файл текстуры.
TEXTURES = {
    "@METAL@": "metal_tile.png",
    "@PANEL_PURPLE@": "panel_purple.png",
    "@PANEL@": "panel.png",
    "@SCANLINE@": "scanline.png",
    "@BUTTON_HOVER@": "button_hover.png",
    "@BUTTON@": "button.png",
    "@BAR@": "bar.png",
}


def _texture(name: str) -> str:
    """Путь к текстуре в виде, понятном QSS."""

    return (UI_DIR / name).as_posix()


def load_window_style() -> str:
    """Читает QSS и подставляет абсолютные пути к текстурам."""

    template = STYLE_FILE.read_text(encoding="utf-8")

    for placeholder, name in TEXTURES.items():
        template = template.replace(placeholder, _texture(name))

    return template


WINDOW_STYLE = load_window_style()
