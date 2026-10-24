# Giperion/app/ui/conference_job.py                                 v001
# Фоновый расчёт параллельного совета моделей.
# Последнее изменение: первый режим конференции.

import threading

from terminal.core.conference import ConferenceReply, ask_conference


class ConferenceJob:
    """Считает ответы нескольких моделей, не блокируя окно."""

    def __init__(
        self,
        user_message: str,
        context: str,
        participants: list[dict],
    ) -> None:
        self.replies: list[ConferenceReply] = []
        self.error: Exception | None = None
        self.done = False

        self._thread = threading.Thread(
            target=self._run,
            args=(user_message, context, participants),
            daemon=True,
        )
        self._thread.start()

    def _run(
        self,
        user_message: str,
        context: str,
        participants: list[dict],
    ) -> None:
        """Спрашивает всех участников и запоминает ответы."""

        try:
            self.replies = ask_conference(
                participants,
                user_message,
                context,
            )
        except Exception as error:  # noqa: BLE001 — ошибку покажет окно
            self.error = error
        finally:
            self.done = True
