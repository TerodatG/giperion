# Giperion/terminal/ui/transcript_messages.py                                  v001
# Добавление, отрисовка и действия с сообщениями.
# Последнее изменение: вынесено из transcript_mixin.

from datetime import datetime

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from terminal.ui.theme import (
    BOT_COLOR,
    BOT_NICKNAME,
    COPY_COLOR,
    EDIT_COLOR,
    STAMP_COLOR,
    STAMP_FORMAT,
    THINKING_DOTS,
    THINKING_TEXT,
)


class TranscriptMessagesMixin:
    """Добавление, отрисовка и действия с сообщениями."""

    @staticmethod
    def _now_stamp() -> str:
        """Возвращает дату и время сообщения."""

        return datetime.now().strftime(STAMP_FORMAT)


    def append_user(self, message: str) -> None:
        """Запоминает и показывает сообщение пользователя."""

        self._finish_typing()

        stamp = self._now_stamp()

        self.chat_log.append(("user", message, stamp))

        self._render_user(message, stamp)


    @staticmethod
    def _message_footer(icons: str, stamp: str) -> str:
        """Собирает низ сообщения: значки слева, дата и время справа."""

        stamp_html = (
            f'<span style="color:{STAMP_COLOR}; font-size:8pt;">'
            f'{stamp}</span>'
        )

        return (
            f'<table width="100%" cellspacing="0" cellpadding="0">'
            f'<tr>'
            f'<td><p style="margin:0;">{icons}</p></td>'
            f'<td><p align="right" style="margin:0;">{stamp_html}</p></td>'
            f'</tr></table>'
        )


    def _render_user(self, message: str, stamp: str = "") -> None:
        """Рисует сообщение пользователя: копирование, правка, время."""

        color = self.colors["user"]

        index = len(self.user_messages)
        self.user_messages.append(message)

        icons = (
            f'<a href="ucopy:{index}" '
            f'style="color:{COPY_COLOR}; text-decoration:none; '
            f'font-size:12pt;">⧉</a> '
            f'<a href="edit:{index}" '
            f'style="color:{EDIT_COLOR}; text-decoration:none; '
            f'font-size:12pt;">✎</a>'
        )

        footer = self._message_footer(icons, stamp)
        style = self._text_style("user")

        self._append(
            f'<p style="margin:6px 0;">'
            f'<b style="color:{color};">Ты:</b> '
            f'<span style="color:{color}; {style}">'
            f'{self._escape(message)}</span></p>{footer}'
        )


    def append_bot(
        self,
        message: str,
        with_copy: bool = True,
        name: str = "",
        role: str = "bot",
    ) -> None:
        """Запоминает и показывает ответ модели.

        Если with_copy включён, добавляет ссылку «копировать», которая
        кладёт текст этого ответа в буфер обмена. name — кто отвечает;
        role — группа стиля: «bot» для ответа ИИ или «data» для текста
        из файла/интернета.
        """

        self._finish_typing()

        stamp = self._now_stamp()
        speaker = name or getattr(
            self,
            "bot_nickname",
            BOT_NICKNAME,
        )

        self.chat_log.append(
            ("bot", message, with_copy, stamp, speaker, role)
        )

        if self._should_type(message):
            self._start_typing(
                message,
                with_copy,
                stamp,
                speaker,
                role,
            )
        else:
            self._render_bot(
                message,
                with_copy,
                stamp,
                speaker,
                role,
            )


    def _render_bot(
        self,
        message: str,
        with_copy: bool,
        stamp: str = "",
        speaker: str = BOT_NICKNAME,
        role: str = "bot",
    ) -> None:
        """Рисует ответ модели: имя, значок копирования и время."""

        copy_link = ""

        if with_copy:
            index = len(self.bot_messages)
            self.bot_messages.append(message)

            # Значок копирования — под последней строкой ответа.
            copy_link = (
                f'<a href="copy:{index}" '
                f'style="color:{COPY_COLOR}; text-decoration:none; '
                f'font-size:12pt;">⧉</a>'
            )

        footer = self._message_footer(copy_link, stamp)

        speaker_color = self._speaker_color(role)
        body_color = self.colors.get(role, BOT_COLOR)
        body_style = self._text_style(role)

        self._append(
            f'<p style="margin:6px 0;">'
            f'<b style="color:{speaker_color};">{speaker}:</b> '
            f'<span style="color:{body_color}; {body_style}">'
            f'{self._escape(message)}</span></p>{footer}'
        )


    def append_abstain(self, name: str) -> None:
        """Пишет в терминал связи, что участник воздержался от ответа."""

        self._finish_typing()

        text = f"«{name}» воздержался от ответа."

        self.chat_log.append(("abstain", text))
        self._render_abstain(text)


    def _render_abstain(self, text: str) -> None:
        """Рисует сообщение о воздержавшемся участнике."""

        color = self.colors.get(
            "system",
            self.colors.get("bot", BOT_COLOR),
        )
        style = self._text_style("system")

        self._append(
            f'<p style="margin:6px 0;">'
            f'<i style="color:{color}; {style}">'
            f'{self._escape(text)}</i></p>'
        )


    def _on_anchor_clicked(self, url) -> None:
        """Обрабатывает значки в истории чата."""

        link = url.toString()

        if link.startswith("ucopy:"):
            self._copy_user_message(link)
        elif link.startswith("copy:"):
            self._copy_bot_message(link)
        elif link.startswith("edit:"):
            self._edit_user_message(link)


    def _copy_bot_message(self, link: str) -> None:
        """Копирует ответ Гипериона в буфер обмена."""

        try:
            index = int(link.split(":", 1)[1])
            text = self.bot_messages[index]
        except (ValueError, IndexError):
            return

        QApplication.clipboard().setText(text)

        self.append_system("Ответ скопирован в буфер обмена.")


    def _copy_user_message(self, link: str) -> None:
        """Копирует сообщение пользователя в буфер обмена."""

        try:
            index = int(link.split(":", 1)[1])
            text = self.user_messages[index]
        except (ValueError, IndexError):
            return

        QApplication.clipboard().setText(text)

        self.append_system("Сообщение скопировано в буфер обмена.")


    def _edit_user_message(self, link: str) -> None:
        """Возвращает сообщение в поле ввода для правки."""

        try:
            position = int(link.split(":", 1)[1])
        except (ValueError, IndexError):
            return

        entry_index = self._user_entry_index(position)

        if entry_index is None:
            return

        text = self.chat_log[entry_index][1]

        del self.chat_log[entry_index]

        self._rebuild_chat()

        self.input.setPlainText(text)

        cursor = self.input.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.input.setTextCursor(cursor)

        self.input.setFocus()


    def _user_entry_index(self, position: int) -> int | None:
        """Находит запись журнала по номеру сообщения пользователя."""

        seen = 0

        for index, entry in enumerate(self.chat_log):
            if entry[0] != "user":
                continue

            if seen == position:
                return index

            seen += 1

        return None


    def append_system(self, message: str) -> None:
        """Запоминает и показывает системное сообщение."""

        self._finish_typing()

        self.chat_log.append(("system", message))

        self._render_system(message)


    def _render_system(self, message: str) -> None:
        """Пишет системное сообщение в отдельное поле."""

        if not hasattr(self, "system_log"):
            return

        self.system_log.appendPlainText(f"[СИСТЕМА]: {message}")
        self.system_log.verticalScrollBar().setValue(
            self.system_log.verticalScrollBar().maximum()
        )


    def append_level_up(self, level: int, rank: str) -> None:
        """Запоминает и показывает заметное сообщение о новом уровне."""

        self._finish_typing()

        self.chat_log.append(("level", level, rank))

        self._render_level_up(level, rank)


    def _render_level_up(self, level: int, rank: str) -> None:
        """Рисует плашку нового уровня текущим цветом."""

        color = self.colors["message"]
        style = self._text_style("message")

        self._append(
            f'<p style="margin:10px 0; padding:8px 12px; '
            f'background-color:#2a0d2e; border-left:4px solid '
            f'{color};">'
            f'<b style="color:{color};">⬆ НОВЫЙ УРОВЕНЬ! '
            f'</b>'
            f'<span style="color:#ffd9fb; {style}">'
            f'Гиперион достиг уровня {level} — {rank}.</span></p>'
        )


    def _rebuild_chat(self) -> None:
        """Перерисовывает чат с текущими цветами и шрифтом."""

        self._cancel_typing()

        self.chat.clear()

        if hasattr(self, "system_log"):
            self.system_log.clear()

        self.bot_messages = []
        self.user_messages = []

        for entry in self.chat_log:
            kind = entry[0]

            if kind == "user":
                self._render_user(entry[1], entry[2])
            elif kind == "bot":
                speaker = (
                    entry[4] if len(entry) > 4 else BOT_NICKNAME
                )
                role = entry[5] if len(entry) > 5 else "bot"
                self._render_bot(
                    entry[1],
                    entry[2],
                    entry[3],
                    speaker,
                    role,
                )
            elif kind == "system":
                self._render_system(entry[1])
            elif kind == "abstain":
                self._render_abstain(entry[1])
            elif kind == "level":
                self._render_level_up(entry[1], entry[2])
            elif kind == "file":
                self._render_file(entry[1], entry[2])

        self._sync_active_chat()

        # Ожидание ответа не теряем: индикатор возвращаем в конец чата.
        if self.answering:
            self.append_thinking(True)


    def append_thinking(self, enabled: bool) -> None:
        """Показывает и прячет индикатор «обрабатываю запрос…»."""

        if enabled:
            self.thinking_frame = 0
            self._append(self._thinking_html())
            self.thinking_timer.start()

            return

        # Ответ уже в чате — строку индикатора убираем целиком.
        self.thinking_timer.stop()
        self._remove_thinking()


    def _find_thinking_block(self):
        """Находит абзац с индикатором ожидания, если он есть."""

        document = self.chat.document()

        for number in range(document.blockCount() - 1, -1, -1):
            block = document.findBlockByNumber(number)

            if THINKING_TEXT in block.text():
                return block

        return None


    def _remove_thinking(self) -> None:
        """Удаляет строку индикатора из истории чата."""

        block = self._find_thinking_block()

        if block is None:
            return

        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.StartOfBlock)

        if cursor.movePosition(
            QTextCursor.NextBlock,
            QTextCursor.KeepAnchor,
        ):
            cursor.removeSelectedText()

            return

        # Индикатор оказался последним абзацем — просто чистим строку.
        cursor = QTextCursor(block)
        cursor.select(QTextCursor.BlockUnderCursor)
        cursor.removeSelectedText()


    def _thinking_html(self) -> str:
        """Строка индикатора ожидания с бегущими точками."""

        dots = "." * (1 + self.thinking_frame % THINKING_DOTS)
        color = self.colors["bot"]
        speaker = getattr(self, "bot_nickname", BOT_NICKNAME)

        return (
            f'<b style="color:{color};">{speaker}:</b> '
            f'<i style="color:{color};">{THINKING_TEXT}{dots}</i>'
        )


    def _animate_thinking(self) -> None:
        """Меняет кадр индикатора ожидания."""

        block = self._find_thinking_block()

        if block is None:
            self.thinking_timer.stop()

            return

        self.thinking_frame += 1

        # Меняем только содержимое абзаца, не трогая сам абзац.
        cursor = QTextCursor(block)
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(
            QTextCursor.EndOfBlock,
            QTextCursor.KeepAnchor,
        )
        cursor.insertHtml(self._thinking_html())


    @staticmethod
    def _escape(message: str) -> str:
        """Готовит текст к вставке в HTML."""

        return (
            message.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

