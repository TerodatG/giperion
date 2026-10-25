# Giperion/tools/prepare_model_avatar.py                            v001
# Готовит слой светящихся линий для анимации аватара модели.
# Последнее изменение: первый вариант — линии и поиск глаза.

import argparse
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage

from config import BASE_DIR

# Порог свечения: зелёный и синий заметно ярче красного.
SCORE_THRESHOLD = 300
BLUE_THRESHOLD = 140

# Насколько синий должен обгонять красный: белое брюхо в линии не берём.
CYAN_SHIFT = 35

# Итоговая ширина слоя: экранный портрет меньше, запас не нужен.
DEFAULT_SIZE = 640


def _pixels(image: QImage) -> np.ndarray:
    """Отдаёт пиксели картинки массивом (высота, ширина, 4)."""

    source = image.convertToFormat(QImage.Format_RGBA8888)

    return np.frombuffer(
        source.bits(),
        dtype=np.uint8,
    ).reshape((source.height(), source.width(), 4)).copy()


def extract_lines(image: QImage) -> QImage:
    """Оставляет на прозрачном фоне только светящиеся линии."""

    pixels = _pixels(image)

    red = pixels[:, :, 0].astype(np.int16)
    green = pixels[:, :, 1].astype(np.int16)
    blue = pixels[:, :, 2].astype(np.int16)

    score = green + blue - red * 0.6

    mask = (
        (score >= SCORE_THRESHOLD)
        & (blue >= BLUE_THRESHOLD)
        & ((blue - red) >= CYAN_SHIFT)
    )

    layer = np.zeros_like(pixels)
    layer[mask] = pixels[mask]
    layer[:, :, 3] = np.where(mask, 255, 0).astype(np.uint8)

    return QImage(
        layer.data,
        image.width(),
        image.height(),
        image.width() * 4,
        QImage.Format_RGBA8888,
    ).copy()


def find_eye(image: QImage) -> tuple[float, float] | None:
    """Ищет самый яркий холодный блик — глаз киборга.

    Возвращает нормированные координаты (0…1). Фон с боке тоже светится,
    поэтому берём верхнюю половину кадра и считаем центр ярчайшего пятна.
    """

    pixels = _pixels(image)

    height, width = pixels.shape[:2]

    red = pixels[:, :, 0].astype(np.int32)
    green = pixels[:, :, 1].astype(np.int32)
    blue = pixels[:, :, 2].astype(np.int32)

    score = green + blue - red

    # Верхняя половина: там голова, а не броня и не нижние огни.
    top = int(height * 0.10)
    bottom = int(height * 0.55)

    region = score[top:bottom, :]

    if region.size == 0:
        return None

    threshold = float(np.percentile(region, 99.98))
    rows, columns = np.where(region >= threshold)

    if len(columns) == 0:
        return None

    weights = region[rows, columns].astype(np.float64)

    x = float(np.average(columns, weights=weights)) / width
    y = float(np.average(rows + top, weights=weights)) / height

    return (round(x, 4), round(y, 4))


def prepare(
    image_path,
    lines_path,
    size: int = DEFAULT_SIZE,
) -> dict:
    """Строит слой линий рядом с исходником и возвращает итог."""

    source = QImage(str(image_path))

    if source.isNull():
        raise SystemExit(f"Не удалось открыть картинку: {image_path}")

    lines = extract_lines(source)

    scale = size / max(source.width(), source.height())

    if scale < 1.0:
        lines = lines.scaled(
            int(round(source.width() * scale)),
            int(round(source.height() * scale)),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )

    lines_path.parent.mkdir(parents=True, exist_ok=True)

    if not lines.save(str(lines_path), "PNG"):
        raise SystemExit(f"Не удалось сохранить слой: {lines_path}")

    return {
        "source": (source.width(), source.height()),
        "lines": (lines.width(), lines.height()),
        "eye": find_eye(source),
    }


def main(argv: list[str] | None = None) -> int:
    """Разбирает аргументы и готовит слой линий."""

    parser = argparse.ArgumentParser(
        description=(
            "Выделяет светящиеся линии аватара в отдельный слой и ищет "
            "координаты глаза для анимации."
        )
    )
    parser.add_argument("--image", default="assets/deepseek_face.png")
    parser.add_argument(
        "--lines",
        default="assets/deepseek_face_lines.png",
    )
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE)

    arguments = parser.parse_args(argv)

    image_path = BASE_DIR / arguments.image
    lines_path = BASE_DIR / arguments.lines

    result = prepare(image_path, lines_path, arguments.size)

    print(f"Исходник: {result['source'][0]}x{result['source'][1]}")
    print(f"Слой линий: {result['lines'][0]}x{result['lines'][1]} -> {lines_path}")

    if result["eye"]:
        print(f"Глаз: {result['eye'][0]}, {result['eye'][1]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
