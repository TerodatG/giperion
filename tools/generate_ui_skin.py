# Giperion/tools/generate_ui_skin.py                               v002
# Генерация текстур интерфейса: тёмный металл, заклёпки, экраны.
# Последнее изменение: фиолетовый экран и планка заголовка.

import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
)
from config import BASE_DIR

UI_DIR = BASE_DIR / "assets" / "ui"

# Тёмная сталь с коричневым оттенком.
BASE_COLOR = (32, 28, 25)

RANDOM_SEED = 20261023


def metal_image(
    width: int,
    height: int,
    seed: int,
    base: tuple[int, int, int] = BASE_COLOR,
    spread: float = 6.0,
) -> QImage:
    """Рисует шумную металлическую основу."""

    rng = np.random.default_rng(seed)

    noise = rng.normal(0.0, spread, (height, width, 1))

    array = np.clip(
        np.array(base, dtype=np.float32) + noise,
        0,
        255,
    ).astype(np.uint8)

    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[:, :, :3] = array
    rgba[:, :, 3] = 255

    return QImage(
        rgba.data,
        width,
        height,
        width * 4,
        QImage.Format_RGBA8888,
    ).copy()


def add_streaks(
    painter: QPainter,
    width: int,
    height: int,
    seed: int,
    count: int = 90,
) -> None:
    """Добавляет горизонтальные потёртости металла."""

    rng = random.Random(seed)

    for _ in range(count):
        y = rng.uniform(0, height)
        start = rng.uniform(0, width * 0.6)
        end = start + rng.uniform(width * 0.2, width * 0.7)

        alpha = rng.randint(4, 13)

        if rng.random() < 0.5:
            color = QColor(255, 238, 214, alpha)
        else:
            color = QColor(0, 0, 0, alpha)

        pen = QPen(color, rng.uniform(0.6, 1.5))
        painter.setPen(pen)
        painter.drawLine(
            QPointF(start, y),
            QPointF(min(end, width), y),
        )


def add_scratches(
    painter: QPainter,
    width: int,
    height: int,
    seed: int,
    count: int = 24,
) -> None:
    """Добавляет редкие царапины."""

    rng = random.Random(seed)

    for _ in range(count):
        x = rng.uniform(0, width)
        y = rng.uniform(0, height)

        length = rng.uniform(6, width * 0.22)
        angle = rng.uniform(-0.9, 0.9)

        color = QColor(220, 205, 185, rng.randint(6, 16))

        pen = QPen(color, rng.uniform(0.6, 1.1))
        painter.setPen(pen)
        painter.drawLine(
            QPointF(x, y),
            QPointF(
                x + np.cos(angle) * length,
                y + np.sin(angle) * length,
            ),
        )


def draw_rivet(
    painter: QPainter,
    x: float,
    y: float,
    radius: float,
) -> None:
    """Рисует заклёпку с блик и тенью."""

    body = QRadialGradient(
        QPointF(x - radius * 0.35, y - radius * 0.35),
        radius * 2.0,
    )
    body.setColorAt(0.0, QColor(126, 116, 102))
    body.setColorAt(0.55, QColor(72, 65, 58))
    body.setColorAt(1.0, QColor(26, 22, 19))

    painter.setPen(Qt.NoPen)
    painter.setBrush(body)
    painter.drawEllipse(QPointF(x, y), radius, radius)

    # Тёмное кольцо вокруг заклёпки.
    painter.setBrush(Qt.NoBrush)

    ring = QPen(QColor(8, 6, 5, 210), 1.0)
    painter.setPen(ring)
    painter.drawEllipse(
        QPointF(x, y),
        radius + 0.6,
        radius + 0.6,
    )

    # Блик.
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(225, 212, 190, 110))
    painter.drawEllipse(
        QPointF(x - radius * 0.32, y - radius * 0.34),
        radius * 0.30,
        radius * 0.24,
    )


def add_bevel(
    painter: QPainter,
    rect: QRectF,
    light_alpha: int = 110,
    dark_alpha: int = 170,
) -> None:
    """Рисует светлую и тёмную фаски по краям плиты."""

    painter.setBrush(Qt.NoBrush)

    light = QPen(QColor(150, 132, 112, light_alpha), 1.0)
    painter.setPen(light)
    painter.drawLine(rect.topLeft(), rect.topRight())
    painter.drawLine(rect.topLeft(), rect.bottomLeft())

    dark = QPen(QColor(0, 0, 0, dark_alpha), 1.0)
    painter.setPen(dark)
    painter.drawLine(rect.bottomLeft(), rect.bottomRight())
    painter.drawLine(rect.topRight(), rect.bottomRight())


def add_red_frame(
    painter: QPainter,
    rect: QRectF,
    strength: float,
) -> None:
    """Рисует красную рамку со свечением вокруг площадки."""

    for index, alpha in enumerate((16, 30, 90)):
        pen = QPen(
            QColor(255, 74, 40, int(alpha * strength)),
            3.0 - index,
        )
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 3.0, 3.0)


def save(image: QImage, name: str) -> None:
    """Сохраняет текстуру в assets/ui."""

    UI_DIR.mkdir(parents=True, exist_ok=True)

    path = UI_DIR / name

    if not image.save(str(path), "PNG"):
        raise RuntimeError(f"Не удалось сохранить текстуру: {path}")

    print(f"Сохранено: {path}")


def build_tile() -> None:
    """Фоновая текстура окна: тёмный металл с потёртостями."""

    size = 192

    image = metal_image(size, size, seed=1, base=(22, 19, 17))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    add_streaks(painter, size, size, seed=2, count=140)
    add_scratches(painter, size, size, seed=3, count=30)

    painter.end()

    save(image, "metal_tile.png")


def draw_screen(
    painter: QPainter,
    rect: QRectF,
    top_color: QColor,
    bottom_color: QColor,
    glow_color: QColor,
) -> None:
    """Рисует светящийся экран внутри металлической рамки."""

    gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    gradient.setColorAt(0.0, top_color)
    gradient.setColorAt(1.0, bottom_color)

    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(rect, 3.0, 3.0)

    # Внутреннее свечение у кромки экрана.
    for index, alpha in enumerate((44, 24)):
        pen = QPen(
            QColor(
                glow_color.red(),
                glow_color.green(),
                glow_color.blue(),
                alpha,
            ),
            4.0 - index * 2,
        )
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(
            rect.adjusted(1.5, 1.5, -1.5, -1.5),
            3.0,
            3.0,
        )


def build_scanline_tile() -> None:
    """Тайл строчной текстуры экрана (повторяется без растяжения)."""

    size = 4

    rgba = np.zeros((size, size, 4), dtype=np.uint8)

    # Две прозрачные строки и две затемнённые — мягкая развёртка.
    rgba[2, :, 3] = 58
    rgba[3, :, 3] = 26

    image = QImage(
        rgba.data,
        size,
        size,
        size * 4,
        QImage.Format_RGBA8888,
    ).copy()

    save(image, "scanline.png")


def build_panel(
    name: str,
    screen: tuple[QColor, QColor, QColor] | None = None,
) -> None:
    """Плита панели: кант, фаска, заклёпки и, если нужно, экран."""

    size = 96
    inset = 14.0

    image = metal_image(size, size, seed=11, base=(30, 26, 23))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    add_streaks(painter, size, size, seed=12, count=80)
    add_scratches(painter, size, size, seed=13, count=18)

    # Тёмный кант по самому краю.
    painter.setPen(QPen(QColor(8, 6, 5), 1.0))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(QRectF(0.5, 0.5, size - 1, size - 1))

    add_bevel(
        painter,
        QRectF(1.5, 1.5, size - 3, size - 3),
        light_alpha=95,
        dark_alpha=180,
    )

    if screen is not None:
        draw_screen(
            painter,
            QRectF(inset, inset, size - inset * 2, size - inset * 2),
            screen[0],
            screen[1],
            screen[2],
        )

    rivet_offset = 10.0

    for x, y in (
        (rivet_offset, rivet_offset),
        (size - rivet_offset, rivet_offset),
        (rivet_offset, size - rivet_offset),
        (size - rivet_offset, size - rivet_offset),
    ):
        draw_rivet(painter, x, y, 3.4)

    painter.end()

    save(image, name)


def build_bar() -> None:
    """Планка заголовка: металл, заклёпки по краям и красная искра."""

    width, height = 160, 40

    image = metal_image(width, height, seed=31, base=(36, 31, 27))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    add_streaks(painter, width, height, seed=32, count=70)

    painter.setPen(QPen(QColor(8, 6, 5), 1.0))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(QRectF(0.5, 0.5, width - 1, height - 1))

    add_bevel(
        painter,
        QRectF(1.5, 1.5, width - 3, height - 3),
        light_alpha=100,
        dark_alpha=175,
    )

    # Красная полоса у нижней кромки планки.
    for y, alpha in ((height - 2, 90), (height - 1, 170)):
        gradient = QLinearGradient(0, y, width, y)
        gradient.setColorAt(0.0, QColor(255, 74, 40, 0))
        gradient.setColorAt(0.5, QColor(255, 90, 50, alpha))
        gradient.setColorAt(1.0, QColor(255, 74, 40, 0))

        painter.setPen(Qt.NoPen)
        painter.fillRect(QRectF(0, y, width, 1), gradient)

    for x, y in ((5.0, 5.0), (width - 5.0, 5.0)):
        draw_rivet(painter, x, y, 2.6)

    painter.end()

    save(image, "bar.png")


def build_button(name: str, hover: bool) -> None:
    """Плита кнопки: площадка под текст и красная рамка."""

    width, height = 96, 48

    base = (44, 36, 30) if hover else (34, 28, 24)

    image = metal_image(
        width,
        height,
        seed=22 if hover else 21,
        base=base,
    )

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    add_streaks(painter, width, height, seed=23, count=40)

    painter.setPen(QPen(QColor(8, 6, 5), 1.0))
    painter.setBrush(Qt.NoBrush)
    painter.drawRect(QRectF(0.5, 0.5, width - 1, height - 1))

    add_bevel(
        painter,
        QRectF(1.5, 1.5, width - 3, height - 3),
        light_alpha=90,
        dark_alpha=170,
    )

    # Тёмная площадка под текст.
    platform = QRectF(11, 11, width - 22, height - 22)

    gradient = QLinearGradient(
        platform.topLeft(),
        platform.bottomLeft(),
    )
    gradient.setColorAt(0.0, QColor(16, 13, 11, 235))
    gradient.setColorAt(1.0, QColor(9, 7, 6, 235))

    painter.setPen(Qt.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(platform, 2.5, 2.5)

    add_red_frame(
        painter,
        platform,
        1.5 if hover else 0.75,
    )

    for x, y in (
        (6.5, 6.5),
        (width - 6.5, 6.5),
        (6.5, height - 6.5),
        (width - 6.5, height - 6.5),
    ):
        draw_rivet(painter, x, y, 2.3)

    painter.end()

    save(image, name)


def main() -> None:
    """Собирает все текстуры интерфейса."""

    application = QGuiApplication([])

    random.seed(RANDOM_SEED)

    build_tile()
    build_panel("panel.png")
    build_panel(
        "panel_purple.png",
        screen=(
            QColor(78, 16, 78),
            QColor(30, 7, 32),
            QColor(236, 96, 236),
        ),
    )
    build_bar()
    build_button("button.png", hover=False)
    build_button("button_hover.png", hover=True)
    build_scanline_tile()

    application.quit()


if __name__ == "__main__":
    main()
