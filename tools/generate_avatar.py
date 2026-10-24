# Giperion/tools/generate_avatar.py                               v002
# Генерация образа Гипериона: цифровое лицо из светящихся узлов.
# Последнее изменение: убрана неиспользуемая функция glow_line.

import math
import os
import random

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

from config import BASE_DIR

SIZE = 900
RANDOM_SEED = 20261022

CYAN = QColor(95, 232, 255)
MINT = QColor(88, 255, 176)
WHITE = QColor(220, 250, 255)

OUTPUT_FILE = BASE_DIR / "assets" / "hyperion_face_wireframe.png"


# --- Вспомогательные приёмы рисования ---


def point(u: float, v: float) -> QPointF:
    """Переводит доли холста в пиксели."""

    return QPointF(u * SIZE, v * SIZE)


def glow_polyline(
    painter: QPainter,
    points: list[tuple[float, float]],
    color: QColor,
    core_width: float = 1.4,
    closed: bool = False,
) -> None:
    """Рисует светящуюся ломаную по долям холста."""

    path_points = [point(u, v) for u, v in points]

    if closed:
        path_points.append(path_points[0])

    for width, alpha in ((7.0, 12), (3.5, 34), (core_width, 210)):
        line_color = QColor(color)
        line_color.setAlpha(alpha)

        pen = QPen(line_color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        painter.setPen(pen)
        painter.drawPolyline(path_points)


def glow_path(
    painter: QPainter,
    path: QPainterPath,
    color: QColor,
    core_width: float = 1.4,
) -> None:
    """Рисует светящийся контур произвольной формы."""

    for width, alpha in ((6.0, 14), (3.0, 36), (core_width, 220)):
        line_color = QColor(color)
        line_color.setAlpha(alpha)

        pen = QPen(line_color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.RoundCap)

        painter.setPen(pen)
        painter.drawPath(path)


def glow_dot(
    painter: QPainter,
    u: float,
    v: float,
    radius: float,
    color: QColor,
    alpha: int = 255,
) -> None:
    """Рисует светящуюся точку-узел."""

    center = point(u, v)

    painter.setPen(Qt.NoPen)

    for multiplier, layer_alpha in (
        (3.2, 24),
        (1.9, 70),
        (1.0, alpha),
    ):
        dot_color = QColor(color)
        dot_color.setAlpha(layer_alpha)

        painter.setBrush(dot_color)
        painter.drawEllipse(
            center,
            radius * multiplier,
            radius * multiplier,
        )


def eye_path(
    center_u: float,
    center_v: float,
    half_width: float,
    half_height: float,
) -> QPainterPath:
    """Строит миндалевидный контур глаза."""

    path = QPainterPath()

    left = point(center_u - half_width, center_v)
    right = point(center_u + half_width, center_v)

    top = point(center_u, center_v - half_height * 1.9)
    bottom = point(center_u, center_v + half_height * 1.9)

    path.moveTo(left)
    path.quadTo(top, right)
    path.quadTo(bottom, left)

    return path


# --- Слои портрета ---


def draw_background(painter: QPainter) -> None:
    """Рисует тёмный фон с мягким свечением в центре."""

    gradient = QRadialGradient(
        point(0.5, 0.44),
        SIZE * 0.62,
    )
    gradient.setColorAt(0.0, QColor(10, 30, 44))
    gradient.setColorAt(0.55, QColor(4, 14, 22))
    gradient.setColorAt(1.0, QColor(1, 4, 9))

    painter.fillRect(
        QRectF(0, 0, SIZE, SIZE),
        gradient,
    )


def draw_dust(painter: QPainter, rng: random.Random) -> None:
    """Добавляет редкую цифровую пыль."""

    painter.setPen(Qt.NoPen)

    for _ in range(170):
        u = rng.random()
        v = rng.random()

        alpha = rng.randint(8, 40)
        radius = rng.uniform(0.4, 1.5)

        color = QColor(CYAN if rng.random() < 0.7 else WHITE)
        color.setAlpha(alpha)

        painter.setBrush(color)
        painter.drawEllipse(point(u, v), radius, radius)


def draw_hud_rings(painter: QPainter) -> None:
    """Рисует тонкие круги и деления вокруг головы."""

    center = point(0.5, 0.44)

    for radius_share, alpha, width in (
        (0.315, 34, 1.0),
        (0.365, 18, 1.0),
    ):
        color = QColor(CYAN)
        color.setAlpha(alpha)

        pen = QPen(color)
        pen.setWidthF(width)
        pen.setStyle(Qt.DashLine)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        radius = SIZE * radius_share

        painter.drawEllipse(center, radius, radius)

    # Деления по кругу.
    for degree in range(0, 360, 10):
        angle = math.radians(degree)

        inner = SIZE * 0.315
        outer = inner + (10 if degree % 30 == 0 else 5)

        start = QPointF(
            center.x() + math.cos(angle) * inner,
            center.y() + math.sin(angle) * inner,
        )
        end = QPointF(
            center.x() + math.cos(angle) * outer,
            center.y() + math.sin(angle) * outer,
        )

        color = QColor(CYAN)
        color.setAlpha(48 if degree % 30 == 0 else 26)

        pen = QPen(color)
        pen.setWidthF(1.0)

        painter.setPen(pen)
        painter.drawLine(start, end)


def draw_mesh(painter: QPainter, rng: random.Random) -> None:
    """Рисует разреженную нейросетевую сетку внутри лица."""

    nodes: list[QPointF] = []

    while len(nodes) < 70:
        u = rng.uniform(0.30, 0.70)
        v = rng.uniform(0.17, 0.70)

        # Точка должна попадать внутрь овала лица.
        ellipse = (
            ((u - 0.5) / 0.195) ** 2
            + ((v - 0.43) / 0.29) ** 2
        )

        if ellipse <= 1.0:
            nodes.append(point(u, v))

    # Соединяем близкие узлы тонкими линиями.
    for index, first in enumerate(nodes):
        distances = []

        for other_index, second in enumerate(nodes):
            if other_index == index:
                continue

            distance = math.hypot(
                first.x() - second.x(),
                first.y() - second.y(),
            )

            distances.append((distance, second))

        distances.sort(key=lambda item: item[0])

        for distance, second in distances[:2]:
            if distance > SIZE * 0.11:
                continue

            fade = 30 * (1.0 - distance / (SIZE * 0.11))

            color = QColor(CYAN)
            color.setAlpha(int(fade))

            pen = QPen(color)
            pen.setWidthF(0.9)

            painter.setPen(pen)
            painter.drawLine(first, second)

    for node in nodes:
        color = QColor(CYAN)
        color.setAlpha(58)

        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(node, 1.6, 1.6)


def draw_face(painter: QPainter) -> None:
    """Рисует контуры лица, глаза, нос и губы."""

    jaw = [
        (0.335, 0.285), (0.335, 0.360), (0.350, 0.450),
        (0.375, 0.535), (0.410, 0.610), (0.455, 0.665),
        (0.500, 0.688), (0.545, 0.665), (0.590, 0.610),
        (0.625, 0.535), (0.650, 0.450), (0.665, 0.360),
        (0.665, 0.285),
    ]

    forehead = [
        (0.335, 0.285), (0.355, 0.225), (0.395, 0.185),
        (0.445, 0.163), (0.500, 0.157), (0.555, 0.163),
        (0.605, 0.185), (0.645, 0.225), (0.665, 0.285),
    ]

    glow_polyline(painter, jaw, CYAN, core_width=1.6)
    glow_polyline(painter, forehead, CYAN, core_width=1.6)

    # Глаза.
    for eye_u in (0.415, 0.585):
        path = eye_path(eye_u, 0.405, 0.058, 0.022)

        glow_path(painter, path, WHITE, core_width=1.5)
        glow_dot(painter, eye_u, 0.405, 8.0, CYAN, alpha=230)

        # Тёмный зрачок с ярким кольцом.
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(3, 8, 12))
        painter.drawEllipse(point(eye_u, 0.405), 6.0, 6.0)

        ring = QColor(WHITE)
        ring.setAlpha(210)

        pen = QPen(ring)
        pen.setWidthF(1.2)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(point(eye_u, 0.405), 6.5, 6.5)

    # Брови.
    left_brow = [
        (0.352, 0.366), (0.380, 0.350), (0.415, 0.347),
        (0.448, 0.355), (0.468, 0.368),
    ]
    right_brow = [
        (0.632, 0.366), (0.604, 0.350), (0.569, 0.347),
        (0.536, 0.355), (0.516, 0.368),
    ]

    glow_polyline(painter, left_brow, MINT, core_width=1.2)
    glow_polyline(painter, right_brow, MINT, core_width=1.2)

    # Нос.
    glow_polyline(
        painter,
        [(0.500, 0.402), (0.497, 0.470), (0.500, 0.530)],
        CYAN,
        core_width=1.2,
    )
    glow_polyline(
        painter,
        [
            (0.462, 0.556), (0.485, 0.566), (0.500, 0.568),
            (0.515, 0.566), (0.538, 0.556),
        ],
        CYAN,
        core_width=1.3,
    )
    glow_dot(painter, 0.468, 0.550, 2.4, CYAN, alpha=180)
    glow_dot(painter, 0.532, 0.550, 2.4, CYAN, alpha=180)

    # Губы.
    upper_lip = [
        (0.437, 0.620), (0.468, 0.607), (0.500, 0.603),
        (0.532, 0.607), (0.563, 0.620),
    ]
    lower_lip = [
        (0.437, 0.620), (0.468, 0.641), (0.500, 0.648),
        (0.532, 0.641), (0.563, 0.620),
    ]

    glow_polyline(painter, upper_lip, CYAN, core_width=1.3)
    glow_polyline(painter, lower_lip, CYAN, core_width=1.3)

    # Узлы на ключевых точках.
    for u, v, radius in (
        (0.335, 0.285, 3.0), (0.665, 0.285, 3.0),
        (0.500, 0.157, 3.0), (0.500, 0.688, 3.2),
        (0.375, 0.535, 2.4), (0.625, 0.535, 2.4),
        (0.410, 0.610, 2.4), (0.590, 0.610, 2.4),
    ):
        glow_dot(painter, u, v, radius, MINT, alpha=210)


def draw_scanline(painter: QPainter) -> None:
    """Рисует сканирующую линию на уровне глаз."""

    y = SIZE * 0.405

    for width, alpha in ((9.0, 12), (4.0, 26), (1.2, 150)):
        color = QColor(MINT)
        color.setAlpha(alpha)

        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.RoundCap)

        painter.setPen(pen)
        painter.drawLine(
            QPointF(SIZE * 0.315, y),
            QPointF(SIZE * 0.685, y),
        )


def draw_vignette(painter: QPainter) -> None:
    """Затемняет края холста."""

    gradient = QRadialGradient(
        point(0.5, 0.45),
        SIZE * 0.62,
    )
    gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
    gradient.setColorAt(0.65, QColor(0, 0, 0, 50))
    gradient.setColorAt(1.0, QColor(0, 0, 0, 190))

    painter.fillRect(
        QRectF(0, 0, SIZE, SIZE),
        gradient,
    )


def main() -> None:
    """Собирает портрет и сохраняет его в assets."""

    application = QGuiApplication([])

    image = QImage(
        SIZE,
        SIZE,
        QImage.Format_ARGB32,
    )
    image.fill(QColor(1, 4, 9))

    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)

    rng = random.Random(RANDOM_SEED)

    draw_background(painter)
    draw_dust(painter, rng)
    draw_hud_rings(painter)
    draw_mesh(painter, rng)
    draw_face(painter)
    draw_scanline(painter)
    draw_vignette(painter)

    painter.end()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not image.save(str(OUTPUT_FILE), "PNG"):
        raise RuntimeError(
            f"Не удалось сохранить образ: {OUTPUT_FILE}"
        )

    # Приложение нужно только для инициализации графики.
    application.quit()

    print(f"Образ сохранён: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
