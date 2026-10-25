# Giperion/terminal/ui/transcript_render.py                                  v001
# Лента сообщений и эмуляция печати.
# Последнее изменение: вынесено из transcript_mixin.


from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit

from terminal.ui.theme import (
    BOT_COLOR,
    COPY_COLOR,
    TEXT_STYLE_CSS,
    TYPING_STEP_MS,
)


class TranscriptRenderMixin:
    """Лента сообщений и эмуляция печати."""

    def _build_system_log(self) -> None:
        """Создаёт отдельное поле системных сообщений над вводом."""

        panel = self.window.chatPanel
        layout = panel.layout()

        if layout is None:
            return

        self.system_log = QPlainTextEdit(panel)
        self.system_log.setObjectName("systemLog")
        self.system_log.setReadOnly(True)
        self.system_log.setMaximumBlockCount(200)
        self.system_log.setFocusPolicy(Qt.ClickFocus)
        self.system_log.setFixedHeight(78)

        input_index = layout.indexOf(self.input)

        if input_index >= 0:
            layout.insertWidget(input_index, self.system_log)
        else:
            layout.addWidget(self.system_log)

        layout.setStretch(layout.indexOf(self.chat), 4)
        layout.setStretch(layout.indexOf(self.system_log), 0)
        layout.setStretch(layout.indexOf(self.input), 0)

        # Поле ввода становится чуть ниже, освобождая место системе.
        self.input.setFixedHeight(128)


    def _append(self, html: str) -> None:
        """Добавляет готовый HTML-блок в историю чата."""

        self.chat.append(html)
        self.chat.moveCursor(QTextCursor.End)


    def _should_type(self, message: str) -> bool:
        """Нужно ли печатать этот ответ по символам."""

        return bool(
            message
            and self.response_settings.get("typing_enabled", True)
            and not self.response_settings.get(
                "typing_instant",
                False,
            )
        )


    def _speaker_color(self, role: str) -> str:
        """Цвет имени говорящего: у сенаторов — цвет их группы."""

        if str(role).startswith("senator"):
            return self.colors.get(role, BOT_COLOR)

        return self.colors.get("bot", BOT_COLOR)


    def _role_font_size(self, role: str) -> int:
        """Размер шрифта группы: свой или общий размер чата."""

        sizes = getattr(self, "font_sizes", {})
        size = sizes.get(role, 0)

        if isinstance(size, int) and size > 0:
            return size

        return int(getattr(self, "chat_font_size", 0))


    def _text_style(self, role: str) -> str:
        """CSS-фрагмент вида шрифта для группы текста."""

        style = self.styles.get(role, "normal")
        css = TEXT_STYLE_CSS.get(style, "")

        size = self._role_font_size(role)
        base_size = int(getattr(self, "chat_font_size", 0))

        if size > 0 and size != base_size:
            css += f"font-size:{size}pt;"

        return css


    def _typing_format(self, role: str = "bot") -> QTextCharFormat:
        """Формат символов, которые дописываются в чат."""

        text_format = QTextCharFormat()
        text_format.setForeground(
            QColor(
                self.colors.get(
                    role,
                    self.colors.get("bot", BOT_COLOR),
                )
            )
        )

        font = QFont(self.chat.font())
        size = self._role_font_size(role)

        if size > 0:
            font.setPointSize(size)

        text_format.setFont(font)

        style = self.styles.get(role, "normal")
        text_format.setFontWeight(
            QFont.Bold
            if style in ("bold", "bold_italic")
            else QFont.Normal
        )
        text_format.setFontItalic(
            style in ("italic", "bold_italic")
        )

        return text_format


    def _insert_typing_text(
        self,
        text: str,
        role: str = "bot",
    ) -> None:
        """Дописывает кусок ответа в конец истории."""

        if not text:
            return

        cursor = QTextCursor(self.chat.document())
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text, self._typing_format(role))

        self.chat.setTextCursor(cursor)
        self.chat.ensureCursorVisible()


    def _start_typing(
        self,
        message: str,
        with_copy: bool,
        stamp: str,
        speaker: str,
        role: str = "bot",
    ) -> None:
        """Начинает печатать ответ по символам."""

        copy_link = ""

        if with_copy:
            index = len(self.bot_messages)
            self.bot_messages.append(message)

            copy_link = (
                f'<a href="copy:{index}" '
                f'style="color:{COPY_COLOR}; text-decoration:none; '
                f'font-size:12pt;">⧉</a>'
            )

        speaker_color = self._speaker_color(role)
        body_color = self.colors.get(role, BOT_COLOR)
        body_style = self._text_style(role)

        self._append(
            f'<p style="margin:6px 0;">'
            f'<b style="color:{speaker_color};">{speaker}:</b> '
            f'<span style="color:{body_color}; {body_style}">'
            f'</span></p>'
        )

        self.typing_state = {
            "message": message,
            "position": 0,
            "stamp": stamp,
            "copy_link": copy_link,
            "role": role,
            "speed": max(
                5,
                int(
                    self.response_settings.get(
                        "typing_speed",
                        35,
                    )
                ),
            ),
            "accumulator": 0.0,
        }

        self.typing_timer.start()


    def _type_tick(self) -> None:
        """Дописывает очередную порцию символов."""

        state = self.typing_state

        if state is None:
            self.typing_timer.stop()

            return

        state["accumulator"] += (
            state["speed"] * TYPING_STEP_MS / 1000.0
        )

        count = int(state["accumulator"])

        if count <= 0:
            return

        state["accumulator"] -= count

        message = state["message"]
        start = state["position"]
        end = min(len(message), start + count)

        self._insert_typing_text(
            message[start:end],
            state.get("role", "bot"),
        )

        state["position"] = end

        if end >= len(message):
            self._finish_typing()


    def _finish_typing(self) -> None:
        """Мгновенно дописывает остаток ответа и его подпись."""

        state = self.typing_state

        if state is None:
            return

        message = state["message"]
        position = state["position"]

        if position < len(message):
            self._insert_typing_text(
                message[position:],
                state.get("role", "bot"),
            )

        self.typing_timer.stop()
        self.typing_state = None

        footer = self._message_footer(
            state["copy_link"],
            state["stamp"],
        )

        self._append(f'<p style="margin:0;">{footer}</p>')


    def _cancel_typing(self) -> None:
        """Прерывает печать без добавления подписи."""

        self.typing_timer.stop()
        self.typing_state = None

