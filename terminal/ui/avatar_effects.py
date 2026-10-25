# Giperion/terminal/ui/avatar_effects.py                               v001
# Огоньки и анализ глаз образа.
# Последнее изменение: вынесено из avatar_render.

import math
import random

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPixmap,
    QRadialGradient,
)

from terminal.ui.avatar_data import (
    AVATAR_SPARK_COUNT,
    AVATAR_SPARK_SEED,
    FALLBACK_AVATAR_EYES,
    AvatarSpark,
)

AVATAR_EYES_CACHE = None


class AvatarEffectsMixin:
    """Падающие огоньки и поиск глаз на портрете."""

    def _build_avatar_sparks(self) -> None:
        """Готовит огоньки, которые медленно падают на фоне."""

        rng = random.Random(AVATAR_SPARK_SEED)

        self.avatar_sparks = [
            AvatarSpark(
                x=rng.random(),
                y=rng.random(),
                speed=rng.uniform(0.012, 0.034),
                size=rng.uniform(2.6, 7.0),
                phase=rng.uniform(0.0, math.tau),
            )
            for _ in range(AVATAR_SPARK_COUNT)
        ]

        self.avatar_spark_sprite = self._avatar_spark_sprite()


    @staticmethod
    def _avatar_spark_sprite() -> QPixmap:
        """Рисует мягкий огонёк один раз, чтобы не строить градиент в кадре."""

        size = 32
        sprite = QPixmap(size, size)
        sprite.fill(Qt.transparent)

        painter = QPainter(sprite)
        painter.setRenderHint(QPainter.Antialiasing, True)

        gradient = QRadialGradient(size / 2, size / 2, size / 2)
        gradient.setColorAt(0.0, QColor(238, 255, 255, 235))
        gradient.setColorAt(0.30, QColor(135, 228, 255, 145))
        gradient.setColorAt(1.0, QColor(30, 120, 220, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(0, 0, size, size)
        painter.end()

        return sprite


    def _advance_sparks(self, dt: float) -> None:
        """Сдвигает огоньки вниз; ушедшие возвращаются наверх."""

        for spark in self.avatar_sparks:
            spark.y += spark.speed * dt

            if spark.y > 1.0:
                spark.y -= 1.0


    def _draw_avatar_sparks(
        self,
        painter: QPainter,
        target: QRectF,
        dt: float,
    ) -> None:
        """Рисует падающие огоньки — только у моделей со своей анимацией."""

        if not self.avatar_sparks or self.avatar_spark_sprite.isNull():
            return

        self._advance_sparks(dt)

        scale = max(0.6, target.width() / 300.0)

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)

        for spark in self.avatar_sparks:
            # Ближе к лицу — тише: огоньки остаются фоном.
            dx = spark.x - 0.5
            dy = spark.y - 0.42
            distance = math.hypot(dx, dy)
            edge = min(1.0, distance / 0.42)

            flicker = 0.7 + 0.3 * math.sin(
                self.avatar_time * 1.6 + spark.phase
            )
            alpha = 0.75 * (0.2 + 0.8 * edge) * flicker

            if alpha <= 0.03:
                continue

            size = spark.size * scale
            x = target.x() + spark.x * target.width() - size / 2
            y = target.y() + spark.y * target.height() - size / 2

            painter.setOpacity(alpha)
            painter.drawPixmap(
                QRectF(x, y, size, size),
                self.avatar_spark_sprite,
                QRectF(0, 0, 32, 32),
            )

        painter.restore()


    def _find_avatar_eyes(self) -> list[tuple[float, float]]:
        """Находит центры светящихся глаз на портрете."""

        global AVATAR_EYES_CACHE

        if AVATAR_EYES_CACHE is not None:
            return AVATAR_EYES_CACHE

        image = self.avatar_pixmap.toImage().convertToFormat(
            QImage.Format_RGBA8888
        )

        width = image.width()
        height = image.height()

        pixels = np.frombuffer(
            image.bits(),
            dtype=np.uint8,
        ).reshape((height, width, 4)).copy()

        red = pixels[:, :, 0].astype(np.int16)
        green = pixels[:, :, 1].astype(np.int16)
        blue = pixels[:, :, 2].astype(np.int16)

        score = green + blue - red

        top = int(height * 0.28)
        bottom = int(height * 0.58)
        left_border = int(width * 0.14)
        right_border = int(width * 0.86)

        eyes = []

        for half_left, half_right in (
            (left_border, width // 2),
            (width // 2, right_border),
        ):
            region = score[top:bottom, half_left:half_right]

            if region.size == 0:
                continue

            threshold = max(
                float(np.percentile(region, 99.5)),
                330.0,
            )

            rows, columns = np.where(region >= threshold)

            if len(columns) == 0:
                continue

            weights = region[rows, columns].astype(np.float64)

            eye_x = (columns + half_left) / width
            eye_y = (rows + top) / height

            eyes.append(
                (
                    float(np.average(eye_x, weights=weights)),
                    float(np.average(eye_y, weights=weights)),
                )
            )

        if len(eyes) != 2:
            eyes = list(FALLBACK_AVATAR_EYES)

        AVATAR_EYES_CACHE = eyes

        return eyes


    def _avatar_lid_color(self, eye_u: float, eye_v: float) -> QColor:
        """Берёт тон кожи вокруг глаза для века."""

        image = self.avatar_pixmap.toImage().convertToFormat(
            QImage.Format_RGBA8888
        )

        width = image.width()
        height = image.height()

        pixels = np.frombuffer(
            image.bits(),
            dtype=np.uint8,
        ).reshape((height, width, 4)).copy()

        x = int(eye_u * width)
        y = int(eye_v * height)

        left = max(0, x - 70)
        right = min(width, x + 70)
        top = max(0, y - 55)
        bottom = min(height, y + 75)

        colors = pixels[top:bottom, left:right, :3].reshape(-1, 3)
        scores = (
            pixels[top:bottom, left:right, 1].astype(np.int16)
            + pixels[top:bottom, left:right, 2].astype(np.int16)
            - pixels[top:bottom, left:right, 0].astype(np.int16)
        ).reshape(-1)

        # Только спокойная кожа: яркие линии и свечение глаза не берём.
        skin = colors[
            (scores < 230)
            & (colors.max(axis=1) > 25)
        ]

        if len(skin) == 0:
            return QColor(8, 70, 120)

        # Чуть светлее кожи, чтобы веко не выглядело провалом.
        median = np.clip(
            np.median(skin, axis=0) * 1.12,
            0,
            255,
        )

        return QColor(
            int(median[0]),
            int(median[1]),
            int(median[2]),
        )
