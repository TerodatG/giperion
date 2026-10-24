# Giperion/tools/prepare_avatar.py                                v002
# Подготовка образа Гипериона из исходной картинки.
# Последнее изменение: слой светящихся линий для живой анимации.

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage

from config import BASE_DIR

SOURCE_FILE = BASE_DIR / "assets" / "hyperion_face_source.jpg"
OUTPUT_FILE = BASE_DIR / "assets" / "hyperion_face.png"
LINES_FILE = BASE_DIR / "assets" / "hyperion_face_lines.png"

# Пропорции панели образа в окне (ширина / высота).
TARGET_RATIO = 0.88

# Итоговый размер картинки — с запасом под масштабирование.
OUTPUT_WIDTH = 620

# Порог для выделения светящихся линий на портрете.
LINE_SCORE_THRESHOLD = 330
LINE_BLUE_THRESHOLD = 150


def extract_lines(image: QImage) -> QImage:
    """Оставляет на прозрачном фоне только светящиеся линии лица."""

    source = image.convertToFormat(QImage.Format_RGBA8888)

    width = source.width()
    height = source.height()

    pixels = np.frombuffer(
        source.bits(),
        dtype=np.uint8,
    ).reshape((height, width, 4)).copy()

    red = pixels[:, :, 0].astype(np.int16)
    green = pixels[:, :, 1].astype(np.int16)
    blue = pixels[:, :, 2].astype(np.int16)

    score = green + blue - red * 0.6

    mask = (
        (score >= LINE_SCORE_THRESHOLD)
        & (blue >= LINE_BLUE_THRESHOLD)
    )

    layer = np.zeros_like(pixels)
    layer[mask] = pixels[mask]
    layer[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)

    return QImage(
        layer.data,
        width,
        height,
        width * 4,
        QImage.Format_RGBA8888,
    ).copy()


def main() -> None:
    """Обрезает исходник по центру и сохраняет портрет со слоем линий."""

    application = QGuiApplication([])

    source = QImage(str(SOURCE_FILE))

    if source.isNull():
        raise RuntimeError(
            f"Не удалось открыть исходник: {SOURCE_FILE}"
        )

    width = source.width()
    height = source.height()

    # Берём всю высоту и вырезаем по центру полосу нужных пропорций.
    crop_width = int(height * TARGET_RATIO)

    if crop_width > width:
        crop_width = width

    left = (width - crop_width) // 2

    cropped = source.copy(left, 0, crop_width, height)

    output_height = int(OUTPUT_WIDTH / TARGET_RATIO)

    portrait = cropped.scaled(
        OUTPUT_WIDTH,
        output_height,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not portrait.save(str(OUTPUT_FILE), "PNG"):
        raise RuntimeError(
            f"Не удалось сохранить образ: {OUTPUT_FILE}"
        )

    # Отдельный слой линий нужен анимации: по нему бежит волна света.
    lines = extract_lines(portrait)

    if not lines.save(str(LINES_FILE), "PNG"):
        raise RuntimeError(
            f"Не удалось сохранить слой линий: {LINES_FILE}"
        )

    application.quit()

    print(
        f"Исходник: {width}x{height}, "
        f"кроп: {crop_width}x{height}, "
        f"результат: {portrait.width()}x{portrait.height()}"
    )
    print(f"Сохранено: {OUTPUT_FILE}")
    print(f"Слой линий: {LINES_FILE}")


if __name__ == "__main__":
    main()
