# Giperion/terminal/ui/answer_mixin.py                              v007
# Ввод сообщения, фоновая обработка ответа и показ результата.
# Последнее изменение: дрон отвечает локальным ядром.

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from shared.action_log import add_action
from shared.text_tools import normalize_message
from terminal.core import pending_state
from terminal.core.character_service import get_characteristics
from terminal.core.chatbot import get_response
from terminal.core.conference_catalog import get_selected_mode_id
from terminal.core.conference_roster import (
    select_conference_models,
    senator_role,
)
from terminal.core.evolution_service import get_rank_name
from terminal.core.model_catalog import (
    DEFAULT_MODEL_ID,
    get_model,
)
from terminal.core.model_settings import (
    load_conference_ids,
)
from terminal.core.module_state import is_module_enabled
from terminal.core.session_commands import (
    extract_system_command,
    is_confirmation_command,
    is_exit_command,
)
from terminal.memory.memory import add_message
from terminal.ui.answer_job import AnswerJob
from terminal.ui.conference_job import ConferenceJob
from terminal.ui.theme import ANSWER_POLL_MS, THINKING_DELAY_MS


class AnswerMixin:
    """Методы окна, отвечающие за обработку и показ ответа."""

    def _conference_participants(self) -> list[dict]:
        """Возвращает участников параллельного совета, если он включён."""

        if getattr(self, "attached_pet", None):
            return []

        if not is_module_enabled("conference"):
            return []

        if get_selected_mode_id() != "council":
            return []

        participants = []

        for model_id in load_conference_ids():
            model = get_model(model_id)

            if model is not None:
                participants.append(model)

        # Максимум три места — у моделей с лучшей репутацией.
        return select_conference_models(participants)

    def send_message(self) -> None:
        """Обрабатывает введённое сообщение тем же путём, что и консоль."""

        # Пока ядро думает, новые сообщения не принимаем.
        if self.answering:
            return

        user_message = self.input.toPlainText().strip()

        if not user_message:
            return

        self.input.clear()
        self.append_user(user_message)

        if is_exit_command(user_message):
            add_action("Гиперион завершил работу (окно)")
            self.append_bot("Увидимся!")

            QApplication.quit()

            return

        system_command = extract_system_command(user_message)

        if system_command is not None:
            self._process_system_command(system_command)

            return

        if (
            pending_state.has_pending_action()
            and is_confirmation_command(user_message)
        ):
            self._process_system_command(
                normalize_message(user_message)
            )

            return

        # Запоминаем уровень до ответа, чтобы заметить рост.
        previous_level = get_characteristics()["level_number"]

        # История без текущей реплики: она уйдёт в запрос отдельной строкой.
        model_context = self._context_for_model(
            exclude_last_user=True
        )
        participants = self._conference_participants()

        # Пауза с индикатором: ядро «обдумывает» ответ.
        self._set_answering(True)

        if participants:
            QTimer.singleShot(
                THINKING_DELAY_MS,
                lambda: self._conference_answer(
                    user_message,
                    previous_level,
                    model_context,
                    participants,
                ),
            )

            return

        QTimer.singleShot(
            THINKING_DELAY_MS,
            lambda: self._answer(
                user_message,
                previous_level,
                model_context,
            ),
        )

    def _answer(
        self,
        user_message: str,
        previous_level: int,
        context: str = "",
    ) -> None:
        """Запускает расчёт ответа в фоне, не замораживая окно."""

        if not self.answering:
            return

        pet = getattr(self, "attached_pet", None)
        job = AnswerJob(
            user_message,
            context,
            local_only=pet is not None,
            persona=pet,
        )

        self._poll_answer(
            job,
            user_message,
            previous_level,
            self.bot_nickname,
            self.chat_epoch,
        )

    def _conference_answer(
        self,
        user_message: str,
        previous_level: int,
        context: str,
        participants: list[dict],
    ) -> None:
        """Запускает параллельный совет моделей."""

        if not self.answering:
            return

        job = ConferenceJob(
            user_message,
            context,
            participants,
        )

        self._poll_conference(
            job,
            user_message,
            previous_level,
            self.chat_epoch,
        )

    def _poll_conference(
        self,
        job: ConferenceJob,
        user_message: str,
        previous_level: int,
        chat_epoch: int,
    ) -> None:
        """Ждёт ответы участников и показывает их в чате."""

        if not self.answering or chat_epoch != self.chat_epoch:
            return

        if not job.done:
            QTimer.singleShot(
                ANSWER_POLL_MS,
                lambda: self._poll_conference(
                    job,
                    user_message,
                    previous_level,
                    chat_epoch,
                ),
            )

            return

        if job.error is not None:
            add_action(f"Ошибка сената: {job.error}")

            self._local_fallback(
                user_message,
                previous_level,
                chat_epoch,
                "Сенат не смог получить ответы — "
                "отвечает локальный Гиперион.",
            )

            return

        if not job.replies:
            self._local_fallback(
                user_message,
                previous_level,
                chat_epoch,
                "Участники сената не ответили — "
                "отвечает локальный Гиперион.",
            )

            return

        # Ошибки — в системный лог, ответы — в терминал связи.
        answers = [
            reply for reply in job.replies if not reply.error
        ]
        failures = [
            reply for reply in job.replies if reply.error
        ]

        for reply in answers:
            if reply.senator:
                role = senator_role(reply.senator)
            elif reply.model_id == DEFAULT_MODEL_ID:
                role = "bot"
            else:
                role = "external"

            self.append_bot(
                reply.text,
                name=reply.nickname or reply.name,
                role=role,
            )

        self.append_thinking(False)

        for reply in failures:
            add_action(
                f"Сенат, {reply.name}: {reply.text}"
            )
            self.append_system(reply.text)
            self.append_abstain(
                reply.nickname or reply.name
            )

        if not answers:
            # Все участники ошиблись — отвечает локальное ядро.
            self._local_fallback(
                user_message,
                previous_level,
                chat_epoch,
                "Все участники сената не ответили — "
                "отвечает локальный Гиперион.",
            )

            return

        add_message("user", user_message)

        for reply in answers:
            add_message(
                "assistant",
                reply.text,
                model=reply.model_id,
            )

        self._update_chat_context()
        self._set_answering(False)
        self.update_core_panel()
        self._announce_level_up(previous_level)

    def _local_fallback(
        self,
        user_message: str,
        previous_level: int,
        chat_epoch: int,
        note: str = "",
    ) -> None:
        """Отвечает локальным ядром, если модели не справились."""

        if not self.answering or chat_epoch != self.chat_epoch:
            return

        result = get_response(user_message)
        answer, save_to_history = result
        external_error = str(
            getattr(result, "external_error", "")
        )

        if external_error:
            self.append_system(external_error)

            answer = (
                "Я не смог ответить: внешняя модель-помощник "
                "недоступна. Попробуй переформулировать запрос."
            )
            save_to_history = False

        self.append_bot(
            answer,
            name=self.bot_nickname,
            role="bot",
        )
        self.append_thinking(False)

        if note:
            self.append_system(note)

        if save_to_history:
            add_message("user", user_message)
            add_message(
                "assistant",
                answer,
                model=DEFAULT_MODEL_ID,
            )

        self._update_chat_context()
        self._set_answering(False)
        self.update_core_panel()
        self._announce_level_up(previous_level)

    def _poll_answer(
        self,
        job: AnswerJob,
        user_message: str,
        previous_level: int,
        speaker: str,
        chat_epoch: int,
    ) -> None:
        """Ждёт готовый ответ и показывает его в чате."""

        if not self.answering or chat_epoch != self.chat_epoch:
            return

        if not job.done:
            QTimer.singleShot(
                ANSWER_POLL_MS,
                lambda: self._poll_answer(
                    job,
                    user_message,
                    previous_level,
                    speaker,
                    chat_epoch,
                ),
            )

            return

        if job.error is not None:
            add_action(f"Ошибка ядра: {job.error}")

            response = (
                "Не смог обработать запрос. Попробуй "
                "переформулировать."
            )
            save_to_history = False
            answer_role = "bot"
        elif job.model_error:
            # Внешняя модель не ответила: это системное сообщение,
            # а не реплика собеседника.
            add_action(
                f"Ошибка модели: {job.error_reason or job.answer}"
            )
            self.append_system(job.answer)
            self.append_thinking(False)
            self._set_answering(False)

            return
        else:
            response = job.answer
            save_to_history = job.save_to_history
            answer_role = job.role

        delay_ms = self._response_delay_ms()

        if delay_ms > 0:
            QTimer.singleShot(
                delay_ms,
                lambda: self._present_answer(
                    response,
                    user_message,
                    previous_level,
                    speaker,
                    save_to_history,
                    job.model_id,
                    answer_role,
                    chat_epoch,
                ),
            )

            return

        self._present_answer(
            response,
            user_message,
            previous_level,
            speaker,
            save_to_history,
            job.model_id,
            answer_role,
            chat_epoch,
        )

    def _present_answer(
        self,
        response: str,
        user_message: str,
        previous_level: int,
        speaker: str,
        save_to_history: bool,
        model_id: str,
        answer_role: str = "bot",
        chat_epoch: int = -1,
    ) -> None:
        """Показывает готовый ответ после возможной задержки."""

        if not self.answering or chat_epoch != self.chat_epoch:
            return

        # Сначала ответ, потом убираем строку индикатора.
        self.append_bot(
            response,
            name=speaker,
            role=answer_role,
        )
        self.append_thinking(False)
        self._update_chat_context()

        if save_to_history:
            add_message("user", user_message)
            add_message("assistant", response, model=model_id)

        self._set_answering(False)

        self.update_core_panel()
        self._announce_level_up(previous_level)

    def _response_delay_ms(self) -> int:
        """Возвращает дополнительную паузу перед показом ответа."""

        if not self.response_settings.get(
            "delay_enabled",
            False,
        ):
            return 0

        try:
            seconds = float(
                self.response_settings.get(
                    "delay_seconds",
                    0.0,
                )
            )
        except (TypeError, ValueError):
            return 0

        return int(max(0.0, min(10.0, seconds)) * 1000)

    def _set_answering(self, busy: bool) -> None:
        """Включает и выключает ожидание ответа."""

        self.answering = busy
        self.button.setEnabled(not busy)

        if hasattr(self, "chat_list"):
            self.chat_list.setEnabled(not busy)

        if hasattr(self, "new_chat_button"):
            self.new_chat_button.setEnabled(not busy)

        if busy:
            self.append_thinking(True)
        else:
            self.thinking_timer.stop()

    def _announce_level_up(self, previous_level: int) -> None:
        """Показывает в чате сообщение, если уровень вырос."""

        characteristics = get_characteristics()
        current_level = characteristics["level_number"]

        if current_level <= previous_level:
            return

        rank = get_rank_name(current_level)

        self.append_level_up(current_level, rank)

    def _process_system_command(self, command: str) -> None:
        """Выполняет системную команду и показывает ответ."""

        if not command:
            self.append_system(
                "После слова «система» напиши команду. "
                "Например: «Гиперион, система: покажи архивы»."
            )

            return

        response, _ = get_response(
            command,
            is_system_mode=True,
        )

        self.append_system(response)
        self.update_core_panel()
