# Giperion/app/ui/chat_sessions_mixin.py                            v004
# Открытые чаты: создание, переключение, переименование, закрепление, удаление.
# Последнее изменение: поле системных сообщений очищается вместе с чатом.

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QListWidgetItem,
    QMenu,
)

from terminal.core import chat_context, pending_state
from terminal.core.model_settings import (
    get_active_model,
)
from terminal.ui.dialogs_base import ChatRenameDialog, ConfirmDialog


class ChatSessionsMixin:
    """Методы окна, отвечающие только за список открытых чатов."""

    def _sync_active_chat(self) -> None:
        """Сохраняет текущие списки в открытый чат."""

        if not (0 <= self.active_chat_index < len(self.chats)):
            return

        session = self.chats[self.active_chat_index]
        session["chat_log"] = self.chat_log
        session["bot_messages"] = self.bot_messages
        session["user_messages"] = self.user_messages
        session["dialog_state"] = pending_state.get_state()

    def _chat_view_indices(self) -> list[int]:
        """Возвращает порядок чатов: закреплённые сверху, затем по номеру."""

        return sorted(
            range(len(self.chats)),
            key=lambda index: (
                0 if self.chats[index].get("pinned") else 1,
                self.chats[index]["number"],
            ),
        )

    def _refresh_chat_list(self) -> None:
        """Перерисовывает список открытых чатов с закреплёнными сверху."""

        if not hasattr(self, "chat_list"):
            return

        self.chat_list.blockSignals(True)
        self.chat_list.clear()

        active_item = None

        for index in self._chat_view_indices():
            session = self.chats[index]
            pinned = bool(session.get("pinned"))
            label = (
                f"★ {session['name']}"
                if pinned
                else session["name"]
            )

            item = QListWidgetItem(label, self.chat_list)
            item.setData(Qt.UserRole, index)

            tooltip = f"Открытый чат №{session['number']}"

            if pinned:
                tooltip = f"Закреплён · {tooltip}"

            item.setToolTip(tooltip)

            font = item.font()
            font.setBold(pinned)
            item.setFont(font)

            if pinned:
                item.setForeground(QColor("#7cf58f"))

            if index == self.active_chat_index:
                active_item = item

        if active_item is not None:
            self.chat_list.setCurrentItem(active_item)

        self.chat_list.blockSignals(False)

    def _update_chat_context(self) -> None:
        """Обновляет скрытую выжимку активного чата."""

        if not (0 <= self.active_chat_index < len(self.chats)):
            return

        session = self.chats[self.active_chat_index]

        try:
            chat_context.write_chat_context(
                session["context_id"],
                session["name"],
                self.chat_log,
            )
        except OSError:
            # Выжимка — вспомогательные данные, чат не должен падать.
            pass

    def _context_for_model(
        self,
        exclude_last_user: bool = False,
    ) -> str:
        """Возвращает историю чата для запроса к модели.

        Источник — скрытый файл выжимки. Текущая реплика при отправке
        ещё не входит в файл, поэтому дублировать её не нужно.
        """

        if not (0 <= self.active_chat_index < len(self.chats)):
            return ""

        session = self.chats[self.active_chat_index]
        raw = chat_context.read_chat_context(
            session["context_id"]
        )
        lines = [
            line
            for line in raw.splitlines()
            if not line.startswith("#")
            and line.strip() != "(диалог пока пуст)"
        ]
        body = "\n".join(lines).strip()

        if body:
            return body

        log = self.chat_log

        if (
            exclude_last_user
            and log
            and log[-1]
            and log[-1][0] == "user"
        ):
            log = log[:-1]

        return chat_context.build_chat_summary(log)

    def _create_chat(self, announce: bool = True) -> None:
        """Открывает новый независимый чат."""

        self._finish_typing()
        self._cancel_typing()
        self.thinking_timer.stop()

        self._sync_active_chat()

        self.chat_sequence += 1

        active_model = get_active_model()
        base_name = (
            active_model["name"]
            if active_model is not None
            else self.bot_name
        )
        name = f"{base_name} {self.chat_sequence}"

        session = {
            "number": self.chat_sequence,
            "name": name,
            "context_id": chat_context.new_context_id(
                self.chat_sequence
            ),
            "chat_log": [],
            "bot_messages": [],
            "user_messages": [],
            "dialog_state": pending_state.new_state(),
            "pinned": False,
        }

        self.chats.append(session)
        self.active_chat_index = len(self.chats) - 1

        self.chat_log = session["chat_log"]
        self.bot_messages = session["bot_messages"]
        self.user_messages = session["user_messages"]
        pending_state.set_state(session["dialog_state"])
        self._update_chat_context()

        self.chat_epoch += 1
        self.chat.clear()

        if hasattr(self, "system_log"):
            self.system_log.clear()

        self._refresh_chat_list()

        if announce:
            self.append_system(f"Открыт новый чат «{name}».")
            self.append_bot(
                "О чём поговорим?",
                with_copy=False,
            )

    def _activate_chat(self, index: int) -> None:
        """Переключает терминал на выбранный открытый чат."""

        if not (0 <= index < len(self.chats)):
            return

        if index == self.active_chat_index:
            return

        if self.answering:
            self._refresh_chat_list()

            return

        self._finish_typing()
        self._cancel_typing()
        self.thinking_timer.stop()

        self._sync_active_chat()

        session = self.chats[index]
        self.active_chat_index = index
        self.chat_log = session["chat_log"]
        self.bot_messages = session["bot_messages"]
        self.user_messages = session["user_messages"]
        pending_state.set_state(
            session.get("dialog_state")
            or pending_state.new_state()
        )

        self.chat_epoch += 1
        self.chat.clear()
        self._rebuild_chat()
        self._sync_active_chat()
        self._refresh_chat_list()

        if not session["chat_log"]:
            self.append_system(
                f"Открыт чат «{session['name']}»."
            )

    def _chat_row_changed(self, row: int) -> None:
        """Реагирует на выбор чата в правой панели."""

        if row < 0:
            return

        item = self.chat_list.item(row)

        if item is None:
            return

        index = item.data(Qt.UserRole)

        if not isinstance(index, int):
            return

        if index == self.active_chat_index:
            return

        self._activate_chat(index)

    def _chat_item_double_clicked(self, item) -> None:
        """Открывает переименование по двойному щелчку."""

        index = item.data(Qt.UserRole)

        if isinstance(index, int):
            self._rename_chat(index)

    def _chat_menu_from_row(
        self,
        row: int,
        global_position: QPoint,
    ) -> None:
        """Открывает меню действий из кнопки «...» в строке чата."""

        item = self.chat_list.item(row)

        if item is None:
            return

        index = item.data(Qt.UserRole)

        if isinstance(index, int):
            self._open_chat_menu(index, global_position)

    def _chat_list_context_menu(self, position) -> None:
        """Меню чата по правой кнопке: те же действия."""

        item = self.chat_list.itemAt(position)

        if item is None:
            return

        index = item.data(Qt.UserRole)

        if not isinstance(index, int):
            return

        self._open_chat_menu(
            index,
            self.chat_list.viewport().mapToGlobal(position),
        )

    def _open_chat_menu(
        self,
        index: int,
        global_position: QPoint,
    ) -> None:
        """Показывает меню: переименовать, закрепить или удалить."""

        if not (0 <= index < len(self.chats)):
            return

        session = self.chats[index]
        menu = QMenu(self.chat_list)

        rename_action = menu.addAction("Переименовать")
        rename_action.triggered.connect(
            lambda: self._rename_chat(index)
        )

        pin_action = menu.addAction(
            "Открепить" if session.get("pinned") else "Закрепить"
        )
        pin_action.triggered.connect(
            lambda: self._toggle_chat_pin(index)
        )

        menu.addSeparator()

        delete_action = menu.addAction("Удалить")
        delete_action.triggered.connect(
            lambda: self._delete_chat(index)
        )

        menu.exec(global_position)

    def _rename_chat(self, index: int) -> None:
        """Переименовывает открытый чат."""

        if not (0 <= index < len(self.chats)):
            return

        session = self.chats[index]
        dialog = ChatRenameDialog(self.window, session["name"])

        if dialog.exec() != QDialog.Accepted:
            return

        name = dialog.chat_name()

        if not name:
            return

        session["name"] = name

        try:
            chat_context.write_chat_context(
                session["context_id"],
                session["name"],
                session["chat_log"],
            )
        except OSError:
            pass

        self._refresh_chat_list()

    def _toggle_chat_pin(self, index: int) -> None:
        """Закрепляет чат сверху списка или снимает закрепление."""

        if not (0 <= index < len(self.chats)):
            return

        session = self.chats[index]
        session["pinned"] = not bool(session.get("pinned"))

        self._refresh_chat_list()

    def _delete_chat(self, index: int) -> None:
        """Удаляет открытый чат после подтверждения."""

        if not (0 <= index < len(self.chats)):
            return

        if self.answering:
            self.append_system(
                "Дождись ответа, прежде чем удалять чат."
            )

            return

        session = self.chats[index]
        dialog = ConfirmDialog(
            self.window,
            "Удалить чат",
            f"Удалить чат «{session['name']}»?\n"
            "История этого чата будет потеряна.",
        )

        if dialog.exec() != QDialog.Accepted:
            return

        self._sync_active_chat()
        was_active = index == self.active_chat_index

        if was_active:
            self._finish_typing()
            self._cancel_typing()
            self.thinking_timer.stop()

        chat_context.remove_chat_context(session["context_id"])
        self.chats.pop(index)

        if not self.chats:
            self.active_chat_index = -1
            self.chat_log = []
            self.bot_messages = []
            self.user_messages = []
            self.chat_epoch += 1
            self.chat.clear()
            self._create_chat(announce=False)
            self.append_system(
                "Чат удалён. Открыт новый чистый чат."
            )

            return

        if index < self.active_chat_index:
            self.active_chat_index -= 1
        elif was_active:
            self.active_chat_index = min(
                index,
                len(self.chats) - 1,
            )
            active = self.chats[self.active_chat_index]

            self.chat_log = active["chat_log"]
            self.bot_messages = active["bot_messages"]
            self.user_messages = active["user_messages"]
            pending_state.set_state(
                active.get("dialog_state")
                or pending_state.new_state()
            )

            self.chat_epoch += 1
            self.chat.clear()
            self._rebuild_chat()
            self._sync_active_chat()

        self._refresh_chat_list()

        if was_active:
            self.append_system(
                f"Чат «{session['name']}» удалён."
            )

    def _new_chat_clicked(self) -> None:
        """Создаёт новый чат по кнопке «＋ Новый чат»."""

        if self.answering:
            self.append_system(
                "Дождись ответа, прежде чем открывать новый чат."
            )

            return

        self._create_chat(announce=True)

    def _clear_active_terminal(self) -> None:
        """Полностью очищает активный терминал связи."""

        self.thinking_timer.stop()
        self._cancel_typing()
        self.answering = False
        self.button.setEnabled(True)
        self.chat_epoch += 1

        self.chat.clear()

        if hasattr(self, "system_log"):
            self.system_log.clear()

        self.chat_log = []
        self.bot_messages = []
        self.user_messages = []
        pending_state.clear_state()

        self._sync_active_chat()

    def clear_chat(self) -> None:
        """Очищает историю активного чата и напоминает о начале работы."""

        # Незавершённое ожидание ответа сбрасываем: чат уже пуст.
        self._clear_active_terminal()

        self.append_bot(
            "Продолжим. О чём поговорим?",
            with_copy=False,
        )
        self.append_system("История чата очищена.")
        self._sync_active_chat()
        self._update_chat_context()
