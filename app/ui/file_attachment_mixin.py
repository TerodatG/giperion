# Giperion/app/ui/file_attachment_mixin.py                          v001
# Прикрепление и показ текстовых файлов, кнопки очистки и скрепки.
# Последнее изменение: методы вынесены из GiperionWindow как отдельный слой.

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPushButton,
)

from app.core.action_log import add_action
from app.skills.file_reader import (
    FileReadError,
    TEXT_FILE_FILTER,
    read_text_file,
)
from app.ui.theme import DATA_COLOR, STAMP_COLOR
from app.ui.widgets import PaperclipButton


class FileAttachmentMixin:
    """Методы окна для работы с прикреплёнными файлами."""

    def _add_clear_button(self):
        """Добавляет кнопку «Очистить чат» рядом с «Отправить»."""

        clear_button = QPushButton("Очистить чат")
        clear_button.setObjectName("clearButton")
        clear_button.setCursor(Qt.ArrowCursor)

        # Кнопка «Отправить» лежит в ячейке сетки — оборачиваем её
        # в горизонтальную раскладку вместе с новой кнопкой.
        parent = self.button.parentWidget()
        parent_layout = parent.layout()

        send_index = parent_layout.indexOf(self.button)

        if send_index != -1:
            row, column, row_span, column_span = (
                parent_layout.getItemPosition(send_index)
            )

            parent_layout.removeWidget(self.button)

            buttons_layout = QHBoxLayout()
            buttons_layout.addWidget(self.button)
            buttons_layout.addWidget(clear_button)

            parent_layout.addLayout(
                buttons_layout,
                row,
                column,
                row_span,
                column_span,
            )

        return clear_button

    def _add_attachment_button(self) -> None:
        """Добавляет скрепку в левый нижний угол поля ввода."""

        self.attach_button = PaperclipButton(self.input)
        self.attach_button.set_allowed(
            bool(self.modules.get("files", False))
        )
        self.attach_button.clicked.connect(self.attach_text_file)
        self.attach_button.show()
        self.attach_button.raise_()

        self._position_attachment_button()

    def _position_attachment_button(self) -> None:
        """Держит скрепку у нижнего левого угла поля ввода."""

        if not hasattr(self, "attach_button"):
            return

        self.attach_button.move(
            6,
            max(4, self.input.height() - 31),
        )
        self.attach_button.raise_()

    def attach_text_file(self) -> None:
        """Выбирает текстовый файл и выводит его содержимое в чат."""

        if not self.modules.get("files", False):
            self.append_system(
                "Доступ к файлам выключен. Включи модуль «Файлы ПК» "
                "на панели под портретом."
            )

            return

        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Добавить текстовый файл",
            str(Path.home()),
            TEXT_FILE_FILTER,
        )

        if not path:
            return

        try:
            data = read_text_file(path)
        except (FileReadError, OSError) as error:
            self.append_system(
                f"Не удалось прочитать файл: {error}."
            )

            return

        self.append_file(data)
        add_action(f"Прочитан файл: {data['name']}")

    def append_file(self, data: dict) -> None:
        """Запоминает и показывает прочитанный файл в истории чата."""

        self._finish_typing()

        stamp = self._now_stamp()

        self.chat_log.append(
            ("file", dict(data), stamp)
        )

        self._render_file(data, stamp)

    def _render_file(self, data: dict, stamp: str = "") -> None:
        """Рисует файл: имя, кодировку, размер и текст."""

        color = self.colors.get("data", DATA_COLOR)
        style = self._text_style("data")

        meta = (
            f'<span style="color:{STAMP_COLOR}; font-size:8pt;">'
            f'{data["size"]} Б · {data["encoding"]} · '
            f'{data["full_length"]} симв.</span>'
        )

        text = self._format_file_text(data["text"])

        if data.get("truncated"):
            text += (
                f'<br><span style="color:{STAMP_COLOR};">'
                f'… показаны первые {len(data["text"])} '
                f'символов.</span>'
            )

        footer = self._message_footer("", stamp)

        self._append(
            f'<p style="margin:8px 0 2px 0;">'
            f'<b style="color:{color};">📎 ФАЙЛ:</b> '
            f'<span style="color:{color}; {style}">'
            f'{self._escape(data["name"])}</span> '
            f'{meta}</p>'
            f'<p style="margin:0 0 6px 0; color:{color}; {style} '
            f'font-family:\'Cascadia Mono\', Consolas; '
            f'font-size:9pt;">{text}</p>'
            f'{footer}'
        )

    @staticmethod
    def _format_file_text(text: str) -> str:
        """Сохраняет пробелы и переводы строк при выводе файла."""

        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\t", "    ")
            .replace("  ", "&nbsp;&nbsp;")
            .replace("\n", "<br>")
        )

        return escaped
