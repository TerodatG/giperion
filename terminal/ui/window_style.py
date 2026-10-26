# Giperion/terminal/ui/window_style.py                             v032
# Единая таблица стилей окна: тёмный металл, зелёные экраны и ржавые плиты.
# Последнее изменение: текстуры берутся из папки выбранного скина.

from config import BASE_DIR
from terminal.core.skins import get_skin

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


def load_window_style() -> str:
    """Читает QSS и подставляет абсолютные пути к текстурам."""

    return build_window_style("terminal")


def build_window_style(skin_id: str = "terminal") -> str:
    """Собирает QSS под выбранный скин: текстуры из skins/<id>/."""

    skin = get_skin(skin_id)
    base = get_skin("terminal")

    template = STYLE_FILE.read_text(encoding="utf-8")

    for placeholder, default_name in TEXTURES.items():
        path = skin.texture_path(placeholder)

        if not path.is_file():
            # У скина ещё нет своей текстуры — берём базовую.
            path = base.texture_path(placeholder)

        if not path.is_file():
            path = UI_DIR / default_name

        template = template.replace(placeholder, path.as_posix())

    return template


WINDOW_STYLE = build_window_style()
