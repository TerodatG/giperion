# Giperion/terminal/ui/answer_job.py                                v004
# Фоновый расчёт ответа активной модели для окна.
# Последнее изменение: локальный режим дрона со своей личностью.

import threading

from terminal.core.chatbot import get_response
from terminal.core.model_catalog import (
    DEFAULT_MODEL_ID,
)
from terminal.core.model_engine import get_model_response
from terminal.core.model_settings import (
    get_current_model_id,
)
from terminal.core.pets import record_pet_activity
from terminal.skills.web_search import INTERNET_ANSWER_PREFIX


class AnswerJob:
    """Считает ответ модели в отдельном потоке.

    Окно остаётся живым: бегут точки ожидания, двигается и перерисовывается
    интерфейс. Поток демонический — закрытие окна не ждёт медленный ответ.
    """

    def __init__(
        self,
        user_message: str,
        context: str = "",
        local_only: bool = False,
        persona: dict | None = None,
    ) -> None:
        self.answer = ""
        self.save_to_history = False
        self.error: Exception | None = None
        self.model_error = False
        self.error_reason = ""
        self.done = False

        # Дрон терминала всегда отвечает локальным ядром.
        self.local_only = local_only
        self.persona = persona

        # Группа стиля: у внешних моделей своя группа шрифта.
        self.role = "bot"

        # Кто отвечает: нужно, чтобы история знала автора ответа.
        self.model_id = get_current_model_id()

        self._thread = threading.Thread(
            target=self._run,
            args=(user_message, context),
            daemon=True,
        )
        self._thread.start()

    def _run(
        self,
        user_message: str,
        context: str,
    ) -> None:
        """Вызывает движок модели и запоминает результат."""

        try:
            if self.local_only:
                result = get_response(
                    user_message,
                    persona=self.persona,
                )
                self.answer, self.save_to_history = result
                self.model_error = bool(
                    getattr(result, "external_error", "")
                )
                self.error_reason = str(
                    getattr(result, "external_error", "")
                )
                self.role = "bot"

                if (
                    self.persona is not None
                    and self.persona.get("id")
                    and not self.model_error
                ):
                    lowered = user_message.lower()
                    learned = int(
                        any(
                            word in lowered
                            for word in (
                                "выучи",
                                "запомни",
                                "научи",
                                "новое слово",
                            )
                        )
                    )
                    record_pet_activity(
                        str(self.persona["id"]),
                        learned,
                    )

                return

            result = get_model_response(
                user_message,
                context,
            )

            self.answer, self.save_to_history = result
            self.model_error = bool(
                getattr(result, "error", False)
            )
            self.error_reason = str(
                getattr(result, "reason", "")
            )

            if self.model_error:
                self.role = "bot"
            elif self.model_id != DEFAULT_MODEL_ID:
                # Внешняя модель рисуется отдельной группой шрифта.
                self.role = "external"
            elif self.answer.startswith(
                INTERNET_ANSWER_PREFIX
            ):
                # Гиперион отвечает выжимкой поиска — это данные из сети.
                self.role = "data"
        except Exception as error:  # noqa: BLE001 — ошибку покажет окно
            self.error = error
        finally:
            self.done = True
