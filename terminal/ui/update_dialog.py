# Giperion/terminal/ui/update_dialog.py                             v001
# Окно «Обновление»: выпуски терминала, скачивание патча и установка.
# Последнее изменение: первый вариант — проверка, журнал и три действия.

import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from terminal.core.app_version import (
    current_released,
    current_version,
    set_skipped,
    skipped_version,
)
from terminal.core.system_info import format_bytes
from terminal.core.update_service import (
    UPDATES_DIR,
    Release,
    UpdateCheck,
    UpdateError,
    apply_update,
    check_updates,
    download_update,
    load_feed_any,
    patch_file_name,
    release_for,
)
from terminal.ui.dialog_text import (
    build_updates_html,
    format_release_date,
)
from terminal.ui.dialogs_base import SkinDialog

# Как часто окно проверяет, закончилась ли фоновая операция.
POLL_MS = 120


class _Job:
    """Фоновая операция окна: проверка, скачивание или установка."""

    def __init__(self, function) -> None:
        self.result = None
        self.error: Exception | None = None
        self.done = False

        self._thread = threading.Thread(
            target=self._run,
            args=(function,),
            daemon=True,
        )
        self._thread.start()

    def _run(self, function) -> None:
        """Выполняет операцию и запоминает итог."""

        try:
            self.result = function()
        except Exception as error:  # noqa: BLE001 — ошибку покажет окно
            self.error = error
        finally:
            self.done = True


class UpdateDialog(SkinDialog):
    """Окно обновления терминала-агента."""

    def __init__(self, parent) -> None:
        super().__init__(
            parent,
            "Обновление",
            min_width=760,
            min_height=560,
        )

        self.resize(820, 620)

        # Состояние окна: что нашли, что скачали.
        self._check: UpdateCheck | None = None
        self._available: Release | None = None
        self._patched = None
        self._entries: list[dict] = []
        self._channel = "stable"

        self._job: _Job | None = None
        self._on_done = None

        self._poll = QTimer(self)
        self._poll.setInterval(POLL_MS)
        self._poll.timeout.connect(self._poll_job)

        self._build_body()
        self._load_initial()

    # --- Сборка окна ---

    def _build_body(self) -> None:
        """Собирает журнал выпусков, строку состояния и кнопки."""

        layout = self.body_layout

        title = QLabel("ОБНОВЛЕНИЕ", self)
        title.setObjectName("dialogTitle")

        subtitle = QLabel(
            "Обновление терминала-агента: проверка выпусков, скачивание "
            "патча и установка. Патчи сохраняются в папку updates под "
            "именем с версией и датой.",
            self,
        )
        subtitle.setObjectName("dialogHint")
        subtitle.setWordWrap(True)

        self.version_label = QLabel("", self)
        self.version_label.setObjectName("updateVersion")
        self.version_label.setWordWrap(True)

        # Зелёное поле в рамке: журнал выпусков.
        plate = QFrame(self)
        plate.setObjectName("paramsPlate")

        plate_layout = QVBoxLayout(plate)
        plate_layout.setContentsMargins(0, 0, 0, 0)
        plate_layout.setSpacing(0)

        self.log = QTextBrowser(plate)
        self.log.setObjectName("updateLog")
        self.log.setOpenLinks(False)
        self.log.setOpenExternalLinks(False)

        plate_layout.addWidget(self.log)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("updateStatus")
        self.status_label.setWordWrap(True)

        self.check_button = QPushButton("Проверить обновление", self)
        self.download_button = QPushButton("Скачать", self)
        self.update_button = QPushButton("Обновить", self)
        self.skip_button = QPushButton("Пропустить", self)

        for button in (
            self.check_button,
            self.download_button,
            self.update_button,
            self.skip_button,
        ):
            button.setObjectName("updateAction")
            button.setCursor(Qt.ArrowCursor)
            button.setFocusPolicy(Qt.NoFocus)
            button.setMinimumHeight(30)

        self.check_button.clicked.connect(self._on_check)
        self.download_button.clicked.connect(self._on_download)
        self.update_button.clicked.connect(self._on_apply)
        self.skip_button.clicked.connect(self._on_skip)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addWidget(self.check_button)
        actions.addWidget(self.download_button)
        actions.addWidget(self.update_button)
        actions.addWidget(self.skip_button)
        actions.addStretch(1)

        self.close_button = QDialogButtonBox(
            QDialogButtonBox.Close,
            self,
        )
        self.close_button.button(QDialogButtonBox.Close).setText(
            "Закрыть"
        )
        self.close_button.rejected.connect(self.reject)

        actions.addWidget(self.close_button)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.version_label)
        layout.addWidget(plate, 1)
        layout.addWidget(self.status_label)
        layout.addLayout(actions)

        self._refresh_buttons()

    def _entry(self, release: Release, is_new: bool = False) -> dict:
        """Превращает выпуск в запись журнала."""

        return {
            "version": release.version,
            "date": release.date,
            "title": release.title,
            "notes": list(release.notes),
            "is_new": bool(is_new),
        }

    # --- Начальное состояние ---

    def _load_initial(self) -> None:
        """Показывает сведения о последнем установленном выпуске."""

        self.version_label.setText(self._version_text())

        try:
            feed = load_feed_any()
        except UpdateError as error:
            self._show_text(
                f'<p style="color:#ff7a5c;">'
                f"Каталог выпусков недоступен: {error}</p>"
                f'<p style="color:#9fbfa5;">Проверка обновлений покажет '
                f"подробности.</p>"
            )
            self._set_status(
                "Каталог выпусков недоступен — проверь источник.",
                error=True,
            )

            return

        release = (
            release_for(current_version(), feed.releases)
            or feed.releases[0]
        )

        self._channel = feed.channel
        self.version_label.setText(self._version_text())

        self._entries = [self._entry(release)]
        self._render()

        self._set_status(
            f"Установлена версия {current_version()} от "
            f"{format_release_date(current_released())}. "
            "Нажми «Проверить обновление», чтобы узнать о новых выпусках."
        )

    def _version_text(self) -> str:
        """Строка о текущей версии и открытом канале."""

        return (
            f"Версия {current_version()} · "
            f"{format_release_date(current_released())} · "
            f"канал {self._channel}"
        )

    # --- Служебное ---

    def _show_text(self, html: str) -> None:
        """Показывает текст в зелёном поле без журнала."""

        self._entries = []
        self.log.setHtml(html)

    def _render(self) -> None:
        """Перерисовывает журнал и прокручивает его к свежей записи."""

        self.log.setHtml(build_updates_html(self._entries))

        # Свежая запись — сверху: после проверки окно смотрит на неё.
        QTimer.singleShot(0, self._scroll_to_top)

    def _scroll_to_top(self) -> None:
        """Ставит полосу прокрутки на самую свежую запись."""

        try:
            self.log.verticalScrollBar().setValue(0)
        except RuntimeError:
            # Окно уже закрыто — прокручивать нечего.
            pass

    def _set_status(self, text: str, *, error: bool = False) -> None:
        """Пишет строку состояния под журналом."""

        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            "color: #ff7a5c;" if error else "color: #9fbfa5;"
        )

    def _refresh_buttons(self) -> None:
        """Включает только те действия, которые сейчас возможны."""

        busy = self._job is not None

        self.check_button.setEnabled(not busy)
        self.download_button.setEnabled(
            not busy
            and self._available is not None
            and self._available.has_patch
        )
        self.update_button.setEnabled(
            not busy and self._patched is not None
        )
        self.skip_button.setEnabled(
            not busy and self._available is not None
        )

    def _run(self, function, on_done) -> None:
        """Запускает операцию в фоне, чтобы окно не замирало."""

        if self._job is not None:
            return

        self._job = _Job(function)
        self._on_done = on_done
        self._refresh_buttons()
        self._poll.start()

    def _poll_job(self) -> None:
        """Забирает итог фоновой операции."""

        job = self._job

        if job is None or not job.done:
            return

        self._poll.stop()
        self._job = None

        if job.error is not None:
            self._set_status(str(job.error), error=True)
        elif self._on_done is not None:
            self._on_done(job.result)

        self._on_done = None
        self._refresh_buttons()

    # --- Действия ---

    def _on_check(self) -> None:
        """Проверяет, есть ли выпуски новее установленного."""

        self._set_status("Проверяю выпуски…")

        self._run(check_updates, self._checked)

    def _checked(self, check: UpdateCheck) -> None:
        """Показывает итог проверки и дополняет журнал."""

        self._check = check
        self._channel = check.channel or self._channel
        self.version_label.setText(self._version_text())

        if check.error:
            self._set_status(check.error, error=True)

            return

        if not check.new_releases:
            self._available = None
            self._patched = None
            self._set_status(
                f"Обновлений нет: установлена последняя версия "
                f"{check.current} ({check.source})."
            )

            return

        known = {entry["version"] for entry in self._entries}
        fresh = [
            self._entry(release, is_new=True)
            for release in check.new_releases
            if release.version not in known
        ]

        if fresh:
            self._entries = fresh + self._entries
            self._render()

        self._available = check.available

        # Скачанный патч остаётся годным, если версия та же.
        if (
            self._patched is not None
            and self._patched.version != self._available.version
        ):
            self._patched = None

        latest = check.available
        skipped = skipped_version()

        if skipped and latest.version == skipped:
            self._set_status(
                f"Версия {skipped} пропущена — она больше не предлагается. "
                "Проверка покажет следующие выпуски."
            )

            return

        self._set_status(
            f"Доступно обновление {latest.version} от "
            f"{format_release_date(latest.date)}. Нажми «Скачать»."
        )

    def _on_skip(self) -> None:
        """Запоминает версию, которую больше не предлагать."""

        release = self._available

        if release is None:
            return

        set_skipped(release.version)

        self._available = None
        self._patched = None

        self._set_status(f"Версия {release.version} пропущена.")
        self._refresh_buttons()

    def _on_download(self) -> None:
        """Скачивает патч доступного выпуска в папку updates."""

        release = self._available

        if release is None:
            return

        if not release.has_patch:
            self._set_status(
                "В выпуске не указан файл патча — скачивать нечего.",
                error=True,
            )

            return

        self._set_status(
            f"Скачиваю патч {patch_file_name(release)}…"
        )

        self._run(
            lambda: download_update(release),
            self._downloaded,
        )

    def _downloaded(self, patch) -> None:
        """Сообщает, куда лёг патч, и разрешает установку."""

        self._patched = patch

        folder = UPDATES_DIR.name

        self._set_status(
            f"Патч сохранён: {folder}/{patch.path.name} "
            f"({format_bytes(patch.size)}). Нажми «Обновить»."
        )

    def _on_apply(self) -> None:
        """Устанавливает скачанный патч."""

        release = self._available
        patch = self._patched

        if release is None or patch is None:
            return

        self._set_status(
            f"Устанавливаю {release.version}…"
        )

        self._run(
            lambda: apply_update(patch.path, release),
            self._applied,
        )

    def _applied(self, result) -> None:
        """Показывает итог установки и закрывает возможность повторной."""

        self._available = None
        self._patched = None

        backup = (
            f", резервная копия: {Path(result.backup_dir).name}"
            if result.backup_dir is not None
            else ""
        )

        self._set_status(
            f"Установлено {result.version}: файлов {len(result.files)}"
            f"{backup}. Перезапусти терминал, чтобы изменения "
            "вступили в силу."
        )

        self.version_label.setText(self._version_text())
        self._entries = [
            {
                **entry,
                "is_new": False,
            }
            for entry in self._entries
        ]
        self._render()

    # --- Завершение ---

    def closeEvent(self, event) -> None:
        """Останавливает опрос фоновой операции."""

        self._poll.stop()
        self._job = None

        super().closeEvent(event)
