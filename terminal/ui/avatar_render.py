# Giperion/terminal/ui/avatar_render.py                                v001
# Отрисовка и анимация образа: линии, глаза, веки и огоньки.
# Последнее изменение: вынесено из avatar_mixin.

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)

from terminal.ui.avatar_data import (
    AVATAR_FRAME_MS,
)
from terminal.ui.avatar_effects import AvatarEffectsMixin

AVATAR_EYES_CACHE = None


class AvatarRenderMixin(AvatarEffectsMixin):
    """Рисование кадров образа и движение огоньков."""

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
        self._draw_avatar_sparks(
            painter,
            target,
            AVATAR_FRAME_MS / 1000.0,
        )
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
        painter.setOpacity(self.avatar_lines_glow)
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

        painter.setOpacity(self.avatar_lines_band)
        painter.drawPixmap(0, 0, layer)

        painter.restore()


    def _draw_avatar_eyes(
        self,
        painter: QPainter,
        target: QRectF,
        time: float,
    ) -> None:
        """Пульс свечения глаз и редкое мигание."""

        if self.avatar_eye_mode == "pulse":
            self._draw_avatar_pulse(painter, target, time)

            return

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


    def _draw_avatar_pulse(
        self,
        painter: QPainter,
        target: QRectF,
        time: float,
    ) -> None:
        """Медленно разжигает и гасит глаз киборга."""

        if not self.avatar_eyes:
            return

        period = max(1.0, self.avatar_eye_period)
        radius = max(4.0, target.width() * self.avatar_eye_radius)

        wave = 0.5 + 0.5 * math.sin(
            time * 2 * math.pi / period - math.pi / 2
        )

        # Разгорается резче, чем гаснет: у глаза живой, неровный ритм.
        intensity = 0.22 + 0.78 * wave ** 1.7
        glow_radius = radius * (0.86 + 0.22 * intensity)

        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Plus)
        painter.setPen(Qt.NoPen)

        for eye_u, eye_v in self.avatar_eyes:
            center = QPointF(
                target.x() + eye_u * target.width(),
                target.y() + eye_v * target.height(),
            )

            halo = QRadialGradient(center, glow_radius)
            halo.setColorAt(
                0.0,
                QColor(240, 255, 255, int(135 * intensity)),
            )
            halo.setColorAt(
                0.18,
                QColor(150, 238, 255, int(105 * intensity)),
            )
            halo.setColorAt(
                0.50,
                QColor(45, 160, 245, int(48 * intensity)),
            )
            halo.setColorAt(1.0, QColor(8, 50, 120, 0))

            painter.setBrush(QBrush(halo))
            painter.drawEllipse(center, glow_radius, glow_radius)

            core = max(1.2, radius * 0.13)

            painter.setBrush(
                QColor(255, 255, 255, int(235 * intensity))
            )
            painter.drawEllipse(center, core, core)

            painter.setBrush(
                QColor(190, 245, 255, int(110 * intensity))
            )
            painter.drawEllipse(center, core * 0.5, core * 0.5)

        painter.restore()


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
