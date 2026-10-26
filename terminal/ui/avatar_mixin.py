# Giperion/app/ui/avatar_mixin.py                                   v002
# Живой образ Гипериона: загрузка портрета, анимация и свечение.
# Последнее изменение: живая анимация аватара внешней модели.


from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QPixmap,
)
from PySide6.QtWidgets import QSizePolicy

from config import BASE_DIR
from terminal.core.model_catalog import (
    DEFAULT_MODEL_ID,
)
from terminal.core.model_settings import (
    get_active_model,
)
from terminal.ui.avatar_data import (
    AVATAR_FILE,
    AVATAR_FRAME_MS,
    AVATAR_LINES_FILE,
    AvatarSpark,
)
from terminal.ui.avatar_render import AvatarRenderMixin


class AvatarMixin(AvatarRenderMixin):
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

        # Режим глаз: у Гипериона веки, у моделей — медленный пульс.
        self.avatar_eye_mode = "lid"
        self.avatar_eye_radius = 0.085
        self.avatar_eye_period = 4.6

        # Свечение слоя линий: постоянное и бегущая волна.
        self.avatar_lines_glow = 0.20
        self.avatar_lines_band = 0.85

        # Огоньки на фоне: живут только у моделей со своей анимацией.
        self.avatar_sparks: list[AvatarSpark] = []
        self.avatar_spark_sprite = QPixmap()

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

        self.avatar_eye_mode = "lid"
        self.avatar_eye_radius = 0.085
        self.avatar_eye_period = 4.6
        self.avatar_lines_glow = 0.20
        self.avatar_lines_band = 0.85
        self.avatar_sparks = []
        self.avatar_spark_sprite = QPixmap()

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

        # Внешняя модель: свой портрет и, если задано, своя анимация.
        avatar_path = model.get("avatar", "")

        if avatar_path:
            path = BASE_DIR / avatar_path

            if path.exists():
                pixmap = QPixmap(str(path))

                if not pixmap.isNull():
                    self.avatar_pixmap = pixmap

                    animation = model.get("avatar_animation") or {}

                    self._apply_avatar_animation(animation)
                    self.update_avatar_pixmap()

                    if self.avatar_animated:
                        self.avatar_timer.start()

                    return

        # Портрета нет — остаётся пустая рамка.

    def _apply_avatar_animation(self, animation: dict) -> None:
        """Настраивает живой образ внешней модели по каталогу."""

        self.avatar_eye_mode = "pulse"

        self.avatar_eyes = [
            (float(point[0]), float(point[1]))
            for point in animation.get("eyes") or []
        ]

        self.avatar_eye_radius = float(
            animation.get("eye_radius") or 0.085
        )
        self.avatar_eye_period = float(
            animation.get("eye_period") or 4.6
        )
        self.avatar_lines_glow = float(
            animation.get("lines_glow") or 0.20
        )
        self.avatar_lines_band = float(
            animation.get("lines_band") or 0.85
        )

        lines_path = animation.get("lines") or ""

        if lines_path:
            layer = QPixmap(str(BASE_DIR / lines_path))

            if not layer.isNull():
                self.avatar_lines = layer

        if animation.get("particles"):
            self._build_avatar_sparks()

        self.avatar_animated = bool(
            self.avatar_eyes
            or not self.avatar_lines.isNull()
            or self.avatar_sparks
        )

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
