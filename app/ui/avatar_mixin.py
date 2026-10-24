# Giperion/app/ui/avatar_mixin.py                                   v001
# Живой образ Гипериона: загрузка портрета, анимация и свечение.
# Последнее изменение: методы вынесены из GiperionWindow как отдельный слой.

import math

import numpy as np

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy

from app.core.model_registry import DEFAULT_MODEL_ID, get_active_model
from config import BASE_DIR

AVATAR_FILE = BASE_DIR / "assets" / "hyperion_face.png"
AVATAR_LINES_FILE = BASE_DIR / "assets" / "hyperion_face_lines.png"

# Частота кадров живой анимации образа.
AVATAR_FRAME_MS = 40

# Запасные координаты глаз, если на портрете их найти не удалось.
FALLBACK_AVATAR_EYES = ((0.34, 0.47), (0.66, 0.47))

# Координаты глаз считаются один раз за запуск приложения.
AVATAR_EYES_CACHE = None


class AvatarMixin:
    """Методы окна, отвечающие только за образ и его анимацию."""

    def _show_avatar(self) -> None:
        """Готовит рамку портрета и включает анимацию ядра."""

        avatar = self.window.avatarImage

        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(
            "background-color: #070605;"
            " border: 1px solid #2a2119;"
        )

        # Кадры анимации не должны раздувать панель через sizeHint.
        avatar.setSizePolicy(
            QSizePolicy.Ignored,
            QSizePolicy.Ignored,
        )
        avatar.setMinimumSize(80, 60)

        avatar.sizeHint = lambda: QSize(240, 300)
        avatar.minimumSizeHint = lambda: QSize(80, 60)

        self.avatar_pixmap = QPixmap()
        self.avatar_lines = QPixmap()
        self.avatar_scaled_size = None
        self.avatar_time = 0.0
        self.avatar_eyes = []
        self.avatar_lid_colors = []
        self.avatar_animated = False

        # При изменении размера панели образ пересчитывается.
        avatar.resizeEvent = self._on_avatar_resize

        # Живая анимация: дыхание, глаза и бегущая волна по линиям.
        self.avatar_timer = QTimer(self.window)
        self.avatar_timer.setInterval(AVATAR_FRAME_MS)
        self.avatar_timer.timeout.connect(self._animate_avatar)

        self.apply_model_avatar()

    def apply_model_avatar(self) -> None:
        """Ставит портрет активной модели или пустую рамку."""

        avatar = self.window.avatarImage

        self.avatar_timer.stop()

        self.avatar_pixmap = QPixmap()
        self.avatar_lines = QPixmap()
        self.avatar_scaled_size = None
        self.avatar_time = 0.0
        self.avatar_eyes = []
        self.avatar_lid_colors = []
        self.avatar_animated = False

        avatar.setPixmap(QPixmap())
        avatar.setText("")
        avatar.setStyleSheet(
            "background-color: #070605;"
            " border: 1px solid #2a2119;"
        )

        model = get_active_model()

        if hasattr(self, "avatar_caption"):
            if model is None or model["id"] == DEFAULT_MODEL_ID:
                self.avatar_caption.setText("ОБРАЗ ГИПЕРИОНА")
            else:
                self.avatar_caption.setText("ОБРАЗ МОДЕЛИ")

        if model is None or model["id"] == DEFAULT_MODEL_ID:
            self.avatar_pixmap = QPixmap(str(AVATAR_FILE))
            self.avatar_lines = QPixmap(str(AVATAR_LINES_FILE))

            # Запасной вариант, если картинки нет.
            if self.avatar_pixmap.isNull():
                avatar.setText("◈\n\nГИПЕРИОН")

                font = QFont()
                font.setPointSize(20)
                font.setBold(True)

                avatar.setFont(font)
                avatar.setStyleSheet(
                    "background-color: #101820; color: #7ee07e;"
                )

                return

            # Где на портрете глаза и какого цвета кожа у век.
            self.avatar_eyes = self._find_avatar_eyes()
            lid_colors = [
                self._avatar_lid_color(eye_u, eye_v)
                for eye_u, eye_v in self.avatar_eyes
            ]

            # Оба века одного оттенка, чтобы мигание было симметричным.
            if len(lid_colors) == 2:
                unified = QColor(
                    (lid_colors[0].red() + lid_colors[1].red()) // 2,
                    (lid_colors[0].green() + lid_colors[1].green()) // 2,
                    (lid_colors[0].blue() + lid_colors[1].blue()) // 2,
                )
                lid_colors = [unified, unified]

            self.avatar_lid_colors = lid_colors
            self.avatar_animated = True

            self.update_avatar_pixmap()
            self.avatar_timer.start()

            return

        # Внешняя модель: свой портрет, если он есть.
        avatar_path = model.get("avatar", "")

        if avatar_path:
            path = BASE_DIR / avatar_path

            if path.exists():
                pixmap = QPixmap(str(path))

                if not pixmap.isNull():
                    self.avatar_pixmap = pixmap
                    self.update_avatar_pixmap()

                    return

        # Портрета нет — остаётся пустая рамка.

    def _on_avatar_resize(self, event) -> None:
        """Пересчитывает образ под новый размер панели."""

        self.update_avatar_pixmap()

    def update_avatar_pixmap(self) -> None:
        """Масштабирует образ под панель, сохраняя пропорции."""

        avatar = self.window.avatarImage

        if self.avatar_pixmap.isNull():
            return

        size = avatar.size()

        if size.width() < 20 or size.height() < 20:
            return

        if self.avatar_scaled_size == size:
            return

        self.avatar_scaled_size = size

        avatar.setPixmap(
            self.avatar_pixmap.scaled(
                size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    # --- Живой образ ---

    def _animate_avatar(self) -> None:
        """Рисует очередной кадр живой анимации образа."""

        avatar = self.window.avatarImage

        if self.avatar_pixmap.isNull():
            return

        size = avatar.size()

        if size.width() < 20 or size.height() < 20:
            return

        self.avatar_time += AVATAR_FRAME_MS / 1000.0
        time = self.avatar_time

        frame = QPixmap(size)
        frame.fill(QColor(7, 6, 5))

        painter = QPainter(frame)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # Лёгкое дыхание: портрет чуть покачивается и приближается.
        target = self._avatar_target_rect(size, time)

        painter.drawPixmap(
            target,
            self.avatar_pixmap,
            QRectF(self.avatar_pixmap.rect()),
        )

        if not self.avatar_lines.isNull():
            self._draw_avatar_lines(painter, target, size, time)

        self._draw_avatar_eyes(painter, target, time)
        self._draw_avatar_vignette(painter, size)

        painter.end()

        avatar.setPixmap(frame)

    @staticmethod
    def _draw_avatar_vignette(painter: QPainter, size) -> None:
        """Затемняет края кадра, чтобы портрет растворялся в панели."""

        center = QPointF(
            size.width() / 2,
            size.height() * 0.45,
        )
        radius = max(size.width(), size.height()) * 0.78

        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0.52, QColor(7, 6, 5, 0))
        gradient.setColorAt(0.84, QColor(7, 6, 5, 170))
        gradient.setColorAt(1.0, QColor(7, 6, 5, 240))

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRect(
            QRectF(0, 0, size.width(), size.height())
        )

    def _avatar_target_rect(self, size, time: float) -> QRectF:
        """Считает кадр дыхания: зум и небольшое смещение головы.

        Портрет вписывается в панель без искажений, свободное место
        остаётся рамке образа.
        """

        zoom = 1.0 + 0.007 * math.sin(
            time * 2 * math.pi / 7.0
        )
        drift_x = 2.4 * math.sin(
            time * 2 * math.pi / 9.0
        )
        drift_y = 1.6 * math.sin(
            time * 2 * math.pi / 5.5
        )

        aspect = (
            self.avatar_pixmap.width()
            / self.avatar_pixmap.height()
        )

        width = (
            min(size.width(), size.height() * aspect) * zoom
        )
        height = width / aspect

        return QRectF(
            (size.width() - width) / 2 + drift_x,
            (size.height() - height) / 2 + drift_y,
            width,
            height,
        )

    def _draw_avatar_lines(
        self,
        painter: QPainter,
        target: QRectF,
        size,
        time: float,
    ) -> None:
        """Подсвечивает линии лица бегущей волной энергии."""

        painter.save()

        # Постоянное слабое свечение поверх портрета.
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        painter.setOpacity(0.20)
        painter.drawPixmap(
            target,
            self.avatar_lines,
            QRectF(self.avatar_lines.rect()),
        )

        # Волна света: пропускаем слой линий через движущуюся маску.
        layer = QPixmap(size)
        layer.fill(Qt.transparent)

        layer_painter = QPainter(layer)
        layer_painter.setRenderHint(
            QPainter.SmoothPixmapTransform, True
        )
        layer_painter.drawPixmap(
            target,
            self.avatar_lines,
            QRectF(self.avatar_lines.rect()),
        )

        band = (time % 6.0) / 6.0
        band_y = (
            -size.height() * 0.25
            + band * size.height() * 1.5
        )

        gradient = QLinearGradient(
            0.0,
            band_y - size.height() * 0.22,
            0.0,
            band_y + size.height() * 0.22,
        )
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.45, QColor(0, 0, 0, 170))
        gradient.setColorAt(0.5, QColor(0, 0, 0, 235))
        gradient.setColorAt(0.55, QColor(0, 0, 0, 170))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

        layer_painter.setCompositionMode(
            QPainter.CompositionMode_DestinationIn
        )
        layer_painter.fillRect(
            QRectF(0, 0, size.width(), size.height()),
            gradient,
        )
        layer_painter.end()

        painter.setOpacity(0.85)
        painter.drawPixmap(0, 0, layer)

        painter.restore()

    def _draw_avatar_eyes(
        self,
        painter: QPainter,
        target: QRectF,
        time: float,
    ) -> None:
        """Пульс свечения глаз и редкое мигание."""

        blink = self._avatar_blink(time)

        for index, (eye_u, eye_v) in enumerate(self.avatar_eyes):
            center = QPointF(
                target.x() + eye_u * target.width(),
                target.y() + eye_v * target.height(),
            )

            glow_radius = target.width() * 0.085

            if blink < 0.99:
                pulse = 0.5 + 0.5 * math.sin(
                    time * 2 * math.pi / 3.2 + index * 0.9
                )
                alpha = int((30 + 38 * pulse) * (1.0 - blink))

                glow = QRadialGradient(center, glow_radius)
                glow.setColorAt(0.0, QColor(150, 245, 255, alpha))
                glow.setColorAt(
                    0.35,
                    QColor(60, 190, 255, int(alpha * 0.5)),
                )
                glow.setColorAt(1.0, QColor(20, 90, 180, 0))

                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(glow))
                painter.setCompositionMode(
                    QPainter.CompositionMode_Plus
                )
                painter.drawEllipse(
                    center, glow_radius, glow_radius
                )
                painter.setCompositionMode(
                    QPainter.CompositionMode_SourceOver
                )

            if blink > 0.02:
                self._draw_avatar_eyelid(
                    painter, center, target, index, blink
                )

    def _draw_avatar_eyelid(
        self,
        painter: QPainter,
        center: QPointF,
        target: QRectF,
        index: int,
        blink: float,
    ) -> None:
        """Закрывает глаз веком на время мигания."""

        alpha = int(255 * min(1.0, blink * 1.3))
        lid_color = QColor(self.avatar_lid_colors[index])

        lid_width = target.width() * 0.145
        lid_height = max(1.0, target.height() * 0.050 * blink)

        lid_rect = QRectF(
            center.x() - lid_width / 2,
            center.y() - lid_height / 2,
            lid_width,
            lid_height,
        )

        # Лёгкий градиент: верх века светлее, низ — в тени.
        top_color = lid_color.lighter(112)
        top_color.setAlpha(alpha)

        middle_color = QColor(lid_color)
        middle_color.setAlpha(alpha)

        bottom_color = lid_color.darker(115)
        bottom_color.setAlpha(alpha)

        gradient = QLinearGradient(
            lid_rect.topLeft(),
            lid_rect.bottomLeft(),
        )
        gradient.setColorAt(0.0, top_color)
        gradient.setColorAt(0.55, middle_color)
        gradient.setColorAt(1.0, bottom_color)

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(lid_rect)

        # Едва заметная складка сомкнутого века.
        edge = QColor(110, 190, 235, int(55 * blink))

        pen = QPen(edge)
        pen.setWidthF(1.0)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(
            QPointF(lid_rect.left(), center.y()),
            QPointF(lid_rect.right(), center.y()),
        )

    @staticmethod
    def _avatar_blink(time: float) -> float:
        """Возвращает степень закрытия глаз: 0 — открыты, 1 — закрыты."""

        period = 6.8
        duration = 0.26
        phase = time % period

        if phase < period - duration:
            return 0.0

        progress = (phase - (period - duration)) / duration

        return math.sin(progress * math.pi)

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
