# Giperion/terminal/ui/skin_preview.py                               v001
# Миниатюра окна для предпросмотра скина в настройках.
# Последнее изменение: первый вариант — рисунок по палитре скина.

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget

from terminal.core.skins import Skin, get_skin

# Логический размер миниатюры: масштабируется под виджет.
CANVAS_WIDTH = 336
CANVAS_HEIGHT = 214


class SkinPreview(QWidget):
    """Рисует уменьшенное окно терминала в палитре выбранного скина."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setObjectName("skinPreview")
        self.setMinimumSize(320, 210)
        self.skin = get_skin("terminal")

    def set_skin(self, skin: Skin) -> None:
        """Показывает другой скин."""

        self.skin = skin
        self.update()

    def _color(self, key: str) -> QColor:
        """Цвет из палитры скина."""

        return QColor(self.skin.palette.get(key, "#000000"))

    def paintEvent(self, event) -> None:
        """Рисует миниатюру окна с сохранением пропорций."""

        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.Antialiasing,
            bool(self.skin.decor.get("radius", 0)),
        )

        width = max(1, self.width())
        height = max(1, self.height())

        scale = min(width / CANVAS_WIDTH, height / CANVAS_HEIGHT)

        painter.translate(
            (width - CANVAS_WIDTH * scale) / 2,
            (height - CANVAS_HEIGHT * scale) / 2,
        )
        painter.scale(scale, scale)

        self._draw_window(painter)

        painter.end()

    def _draw_window(self, painter: QPainter) -> None:
        """Собирает миниатюру из тех же блоков, что и окно."""

        decor = self.skin.decor
        radius = float(decor.get("radius", 0))

        window = self._color("window")
        panel = self._color("panel")
        border = self._color("border")
        screen = self._color("screen")
        text = self._color("text")
        accent = self._color("accent")
        label = self._color("label")

        # Корпус окна.
        painter.setPen(QPen(border, 2.0))
        painter.setBrush(window)
        painter.drawRoundedRect(
            QRectF(1, 1, CANVAS_WIDTH - 2, CANVAS_HEIGHT - 2),
            radius,
            radius,
        )

        # Планка заголовка.
        painter.setPen(Qt.NoPen)
        painter.setBrush(panel)
        painter.drawRect(QRectF(4, 4, CANVAS_WIDTH - 8, 22))

        painter.setPen(QPen(label, 1.0))
        painter.drawLine(
            QPointF(4, 26),
            QPointF(CANVAS_WIDTH - 4, 26),
        )

        font = QFont("Bahnschrift", 7)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(self._color("title"))
        painter.drawText(
            QRectF(14, 4, 200, 22),
            Qt.AlignLeft | Qt.AlignVCenter,
            "ГИПЕРИОН",
        )

        # Кнопки окна.
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(self._color("button"))

        for offset in (0, 14, 28):
            painter.drawRoundedRect(
                QRectF(
                    CANVAS_WIDTH - 44 + offset,
                    11,
                    10,
                    9,
                ),
                1.5,
                1.5,
            )

        self._draw_portrait_panel(painter, panel, border, screen, accent, label)
        self._draw_terminal_panel(painter, panel, border, screen, text, accent, label)
        self._draw_system_panel(painter, panel, border, accent, label, decor)

        if decor.get("hazard"):
            self._draw_hazard(painter)

        if decor.get("rivets"):
            self._draw_rivets(painter, border)

    def _draw_portrait_panel(
        self,
        painter: QPainter,
        panel: QColor,
        border: QColor,
        screen: QColor,
        accent: QColor,
        label: QColor,
    ) -> None:
        """Левая плита с образом."""

        painter.setPen(QPen(border, 1.0))
        painter.setBrush(panel)
        painter.drawRoundedRect(QRectF(8, 32, 96, 150), 3, 3)

        font = QFont("Bahnschrift", 6)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(label)
        painter.drawText(
            QRectF(12, 35, 88, 12),
            Qt.AlignLeft | Qt.AlignVCenter,
            "ОБРАЗ",
        )

        painter.setPen(QPen(border, 1.0))
        painter.setBrush(screen)
        painter.drawRoundedRect(QRectF(12, 48, 88, 84), 2, 2)

        # Схематичный портрет: ромб и «плечи».
        center = QPointF(56, 84)

        painter.setPen(QPen(accent, 1.4))
        painter.setBrush(Qt.NoBrush)
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(center.x(), center.y() - 16),
                    QPointF(center.x() + 14, center.y()),
                    QPointF(center.x(), center.y() + 16),
                    QPointF(center.x() - 14, center.y()),
                ]
            )
        )
        painter.drawArc(QRectF(36, 96, 40, 28), 0, 180 * 16)

        # Полоса модулей.
        for index in range(4):
            painter.setPen(QPen(border, 1.0))
            painter.setBrush(self._color("button"))
            painter.drawRoundedRect(
                QRectF(14 + index * 22, 140, 18, 18),
                2,
                2,
            )

    def _draw_terminal_panel(
        self,
        painter: QPainter,
        panel: QColor,
        border: QColor,
        screen: QColor,
        text: QColor,
        accent: QColor,
        label: QColor,
    ) -> None:
        """Центральная плита с терминалом связи."""

        painter.setPen(QPen(border, 1.0))
        painter.setBrush(panel)
        painter.drawRoundedRect(QRectF(110, 32, 132, 150), 3, 3)

        font = QFont("Bahnschrift", 6)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(label)
        painter.drawText(
            QRectF(114, 35, 124, 12),
            Qt.AlignLeft | Qt.AlignVCenter,
            "ТЕРМИНАЛ СВЯЗИ",
        )

        screen_rect = QRectF(114, 48, 124, 92)

        painter.setPen(QPen(accent, 1.2))
        painter.setBrush(screen)
        painter.drawRoundedRect(screen_rect, 2, 2)

        if self.skin.decor.get("scanlines"):
            painter.setPen(QPen(QColor(120, 220, 140, 26), 1.0))

            y = int(screen_rect.top()) + 3

            while y < screen_rect.bottom():
                painter.drawLine(
                    QPointF(screen_rect.left() + 2, y),
                    QPointF(screen_rect.right() - 2, y),
                )
                y += 3

        # Строки ответа: первая — говорящий, остальные — текст.
        painter.setPen(
            QPen(QColor(accent.red(), accent.green(), accent.blue()), 1.0)
        )

        font = QFont("Consolas", 6)
        painter.setFont(font)

        painter.setPen(accent)
        painter.drawText(
            QRectF(118, 53, 118, 12),
            Qt.AlignLeft | Qt.AlignVCenter,
            "Гиперион:",
        )

        line_color = QColor(text)
        line_color.setAlpha(190)
        painter.setPen(line_color)

        for index, width in enumerate((96, 108, 84)):
            y = 66 + index * 11
            painter.drawLine(
                QPointF(118, y),
                QPointF(118 + width, y),
            )

        # Поле ввода и кнопка отправки.
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(self._color("window"))
        painter.drawRoundedRect(QRectF(114, 146, 124, 18), 2, 2)

        painter.setPen(QPen(accent, 1.6))
        painter.drawLine(QPointF(121, 155), QPointF(129, 155))
        painter.drawLine(QPointF(125, 151), QPointF(125, 159))

        painter.setPen(Qt.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(QRectF(216, 149, 18, 12), 2, 2)

    def _draw_system_panel(
        self,
        painter: QPainter,
        panel: QColor,
        border: QColor,
        accent: QColor,
        label: QColor,
        decor: dict,
    ) -> None:
        """Правая плита: кнопки системы или бумажная вставка."""

        painter.setPen(QPen(border, 1.0))
        painter.setBrush(panel)
        painter.drawRoundedRect(
            QRectF(248, 32, 80, 150),
            float(decor.get("radius", 0)),
            float(decor.get("radius", 0)),
        )

        font = QFont("Bahnschrift", 6)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(label)
        painter.drawText(
            QRectF(252, 35, 72, 12),
            Qt.AlignLeft | Qt.AlignVCenter,
            "СИСТЕМА",
        )

        if decor.get("paper"):
            paper = QRectF(254, 52, 68, 92)

            painter.setPen(QPen(QColor("#7a5a34"), 1.0))
            painter.setBrush(QColor("#c8a76a"))
            painter.drawRect(paper)

            painter.setPen(QPen(QColor("#5a3a24"), 1.0))
            painter.drawLine(
                QPointF(paper.left() + 6, paper.top() + 14),
                QPointF(paper.right() - 6, paper.top() + 14),
            )

            for index in range(3):
                y = paper.top() + 26 + index * 9
                painter.drawLine(
                    QPointF(paper.left() + 6, y),
                    QPointF(paper.right() - 14, y),
                )

            # Карандашный человечек вместо Vault Boy.
            center = QPointF(paper.center().x() + 4, paper.center().y() + 6)

            painter.drawEllipse(
                QPointF(center.x(), center.y() - 14),
                4,
                4,
            )
            painter.drawLine(
                QPointF(center.x(), center.y() - 10),
                QPointF(center.x(), center.y() + 2),
            )
            painter.drawLine(
                QPointF(center.x() - 7, center.y() - 4),
                QPointF(center.x() + 7, center.y() - 4),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() + 2),
                QPointF(center.x() - 5, center.y() + 12),
            )
            painter.drawLine(
                QPointF(center.x(), center.y() + 2),
                QPointF(center.x() + 5, center.y() + 12),
            )

            return

        for index in range(3):
            painter.setPen(QPen(border, 1.0))
            painter.setBrush(self._color("button"))
            painter.drawRoundedRect(
                QRectF(254, 52 + index * 26, 68, 20),
                float(decor.get("radius", 0)),
                float(decor.get("radius", 0)),
            )

            painter.setPen(QPen(accent, 1.0))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(
                QPointF(262, 62 + index * 26),
                2.4,
                2.4,
            )

    def _draw_hazard(self, painter: QPainter) -> None:
        """Жёлто-чёрная полоса у нижнего края."""

        strip = QRectF(6, 196, CANVAS_WIDTH - 12, 10)

        painter.save()
        painter.setClipRect(strip)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#1a1a14"))
        painter.drawRect(strip)

        painter.setBrush(QColor("#d8b62a"))
        step = 12

        x = strip.left() - step

        while x < strip.right() + step:
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(x, strip.bottom()),
                        QPointF(x + 6, strip.bottom()),
                        QPointF(x + 12, strip.top()),
                        QPointF(x + 6, strip.top()),
                    ]
                )
            )
            x += step

        painter.restore()

    def _draw_rivets(self, painter: QPainter, border: QColor) -> None:
        """Болты по углам корпуса."""

        painter.setPen(QPen(border.darker(140), 1.0))

        for x, y in ((12, 12), (324, 12), (12, 202), (324, 202)):
            painter.setBrush(QColor("#8a7a63"))
            painter.drawEllipse(QPointF(x, y), 3.0, 3.0)

            painter.setPen(QPen(QColor("#d8c8a8"), 1.0))
            painter.drawArc(
                QRectF(x - 3, y - 3, 6, 6),
                45 * 16,
                160 * 16,
            )
            painter.setPen(QPen(border.darker(140), 1.0))
