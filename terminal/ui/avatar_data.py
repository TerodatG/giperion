# Giperion/terminal/ui/avatar_data.py                                  v001
# Данные образа: пути, кадры, глаза и огоньки.
# Последнее изменение: вынесено из avatar_mixin.

from dataclasses import dataclass

from config import BASE_DIR

AVATAR_FILE = BASE_DIR / "assets" / "hyperion_face.png"
AVATAR_LINES_FILE = BASE_DIR / "assets" / "hyperion_face_lines.png"

AVATAR_FRAME_MS = 40
FALLBACK_AVATAR_EYES = ((0.34, 0.47), (0.66, 0.47))
AVATAR_SPARK_COUNT = 40
AVATAR_SPARK_SEED = 20261025


@dataclass
class AvatarSpark:
    """Один огонёк, медленно падающий на фоне образа."""

    x: float
    y: float
    speed: float
    size: float
    phase: float


