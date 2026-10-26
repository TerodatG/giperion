# Giperion/terminal/core/skins.py                                    v002
# Каталог скинов интерфейса: папка skins/<id>/skin.json.
# Последнее изменение: скины читаются из отдельных папок в корне проекта.

import re
from dataclasses import dataclass
from pathlib import Path

from config import BASE_DIR
from shared.storage.json_store import read_json_object
from terminal.core.window_settings import (
    DEFAULT_SKIN,
    load_window_settings,
    save_window_settings,
)

# Каждый скин живёт в своей папке: skins/<id>/skin.json и текстуры рядом.
SKINS_DIR = BASE_DIR / "skins"
SKIN_FILE = "skin.json"

# Запасные значения, если папка скина пропала.
ASSETS_DIR = BASE_DIR / "assets" / "ui"

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")

DEFAULT_PALETTE = {
    "window": "#0d0a08",
    "panel": "#1e1a17",
    "border": "#23421f",
    "screen": "#05100a",
    "text": "#b8f0b0",
    "accent": "#7cf58f",
    "label": "#d09a6a",
    "button": "#1b1512",
    "button_text": "#d8b48e",
    "lamp": "#ff5a3c",
    "title": "#ffb37a",
}

DEFAULT_DECOR = {
    "rivets": False,
    "hazard": False,
    "paper": False,
    "scanlines": True,
    "radius": 4,
}

DEFAULT_TEXTURES = {
    "@METAL@": "metal_tile.png",
    "@PANEL_PURPLE@": "panel_purple.png",
    "@PANEL@": "panel.png",
    "@SCANLINE@": "scanline.png",
    "@BUTTON_HOVER@": "button_hover.png",
    "@BUTTON@": "button.png",
    "@BAR@": "bar.png",
}


@dataclass(frozen=True)
class Skin:
    """Описание скина: палитра, декор и текстуры из его папки."""

    id: str
    name: str
    tagline: str
    description: str
    status: str
    palette: dict
    decor: dict
    textures: dict
    folder: Path

    @property
    def ready(self) -> bool:
        """Можно ли применить скин прямо сейчас."""

        return self.status == "ready"

    @property
    def status_text(self) -> str:
        """Подпись состояния для списка."""

        return "готов" if self.ready else "готовится"

    def texture_path(self, placeholder: str) -> Path:
        """Ищет файл текстуры в папке скина."""

        name = self.textures.get(placeholder) or DEFAULT_TEXTURES.get(
            placeholder,
            "",
        )

        if not name:
            return self.folder / ""

        return self.folder / name


def _clean_palette(value: object) -> dict:
    """Проверяет цвета скина, дополняя недостающие."""

    palette = dict(DEFAULT_PALETTE)

    if not isinstance(value, dict):
        return palette

    for key in DEFAULT_PALETTE:
        color = value.get(key)

        if isinstance(color, str) and color.strip():
            palette[key] = color.strip()[:20]

    return palette


def _clean_decor(value: object) -> dict:
    """Проверяет набор декора."""

    decor = dict(DEFAULT_DECOR)

    if not isinstance(value, dict):
        return decor

    for key in ("rivets", "hazard", "paper", "scanlines"):
        if isinstance(value.get(key), bool):
            decor[key] = value[key]

    radius = value.get("radius")

    if isinstance(radius, int) and not isinstance(radius, bool):
        decor["radius"] = max(0, min(12, radius))

    return decor


def _clean_textures(value: object) -> dict:
    """Проверяет карту «плейсхолдер → файл текстуры»."""

    if not isinstance(value, dict):
        return {}

    textures = {}

    for placeholder, name in value.items():
        if (
            isinstance(placeholder, str)
            and placeholder.startswith("@")
            and isinstance(name, str)
            and name.strip()
        ):
            textures[placeholder] = name.strip()[:80]

    return textures


def _parse_skin(folder: Path) -> Skin | None:
    """Читает skin.json из папки скина."""

    document = read_json_object(folder / SKIN_FILE)

    if not document:
        return None

    skin_id = str(document.get("id") or folder.name).strip()

    if not _ID_PATTERN.fullmatch(skin_id) or skin_id != folder.name:
        return None

    name = " ".join(str(document.get("name") or "").split())

    if not name:
        return None

    status = document.get("status")

    if status not in ("ready", "draft"):
        status = "draft"

    return Skin(
        id=skin_id,
        name=name[:40],
        tagline=str(document.get("tagline") or "")[:80],
        description=str(document.get("description") or "")[:800],
        status=status,
        palette=_clean_palette(document.get("palette")),
        decor=_clean_decor(document.get("decor")),
        textures=_clean_textures(document.get("textures")),
        folder=folder,
    )


def _discover() -> tuple[Skin, ...]:
    """Собирает скины из папки skins/."""

    if not SKINS_DIR.is_dir():
        return ()

    found = []

    for folder in sorted(SKINS_DIR.iterdir()):
        if not folder.is_dir():
            continue

        skin = _parse_skin(folder)

        if skin is not None:
            found.append(skin)

    # Скин по умолчанию — первым, остальные по названию.
    found.sort(key=lambda skin: (skin.id != DEFAULT_SKIN, skin.name))

    return tuple(found)


def _fallback() -> Skin:
    """Скин-заглушка, если папка skins/ пропала."""

    return Skin(
        id=DEFAULT_SKIN,
        name="Терминал",
        tagline="Металл и зелёный фосфор",
        description=(
            "Папка skins/ не найдена: показывается базовая шкура "
            "из assets/ui."
        ),
        status="ready",
        palette=dict(DEFAULT_PALETTE),
        decor=dict(DEFAULT_DECOR),
        textures=dict(DEFAULT_TEXTURES),
        folder=ASSETS_DIR,
    )


SKINS = _discover() or (_fallback(),)
SKIN_IDS = tuple(skin.id for skin in SKINS)


def clean_skin_id(value: object) -> str:
    """Возвращает известный скин или скин по умолчанию."""

    text = str(value or "").strip()

    if text in SKIN_IDS:
        return text

    return SKIN_IDS[0]


def get_skin(skin_id: str) -> Skin:
    """Находит скин по идентификатору."""

    wanted = clean_skin_id(skin_id)

    for skin in SKINS:
        if skin.id == wanted:
            return skin

    return SKINS[0]


def load_skin_id() -> str:
    """Читает выбранный скин из настроек окна."""

    settings = load_window_settings()

    return clean_skin_id(settings.get("skin"))


def save_skin_id(skin_id: str) -> str:
    """Запоминает выбранный скин и возвращает его."""

    chosen = clean_skin_id(skin_id)

    settings = load_window_settings()
    settings["skin"] = chosen
    save_window_settings(settings)

    return chosen
