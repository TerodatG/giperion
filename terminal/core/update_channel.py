# Giperion/terminal/core/update_channel.py                           v001
# Адрес канала обновлений: файлы релиза на GitHub.

import os
import sys

# Готовый канал: каталоги выпусков лежат в ассетах последнего релиза.
RELEASE_FEED_BASE = (
    "https://github.com/TerodatG/giperion/releases/latest/download"
)

# Переменная окружения важнее адреса по умолчанию (удобно для проверки).
FEED_ENV = "GIPERION_UPDATE_FEED"


def feed_platform() -> str:
    """Имя платформы для файла каталога: windows, linux или macos."""

    if sys.platform.startswith("win"):
        return "windows"

    if sys.platform == "darwin":
        return "macos"

    return "linux"


def feed_source() -> str:
    """Адрес каталога выпусков: переменная окружения или GitHub Releases."""

    override = os.environ.get(FEED_ENV, "").strip()

    if override:
        return override

    return f"{RELEASE_FEED_BASE}/releases-{feed_platform()}.json"
