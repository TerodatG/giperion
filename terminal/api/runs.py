# Giperion/terminal/api/runs.py                                        v001
# Фоновые прогоны API: запуск в потоке, статус и отмена.

import threading
import uuid
from datetime import datetime, timezone

from terminal.api import service

# Сколько прогонов держим в памяти.
MAX_RUNS = 50


class RunRecord:
    """Один фоновый прогон."""

    def __init__(self, task: str, project: str) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.task = task
        self.project = project
        self.status = "queued"
        self.result: dict | None = None
        self.error = ""
        self.cancelled = False
        self.started = datetime.now(timezone.utc).isoformat()
        self.finished = ""
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def should_stop(self) -> bool:
        """Сигнал агенту: пора остановиться."""

        return self._stop.is_set()

    def cancel(self) -> bool:
        """Просит прогон остановиться."""

        if self.status in ("done", "failed", "cancelled"):
            return False

        self._stop.set()
        self.status = "cancelling"

        return True

    def payload(self) -> dict:
        """Состояние прогона для API."""

        return {
            "id": self.id,
            "status": self.status,
            "task": self.task[:200],
            "project": self.project,
            "started": self.started,
            "finished": self.finished,
            "error": self.error,
            "result": self.result,
        }

    def start(self, steps: int, policy: str) -> None:
        """Запускает прогон в отдельном потоке."""

        self.status = "running"
        self._thread = threading.Thread(
            target=self._work,
            args=(steps, policy),
            daemon=True,
        )
        self._thread.start()

    def _work(self, steps: int, policy: str) -> None:
        """Выполняет задачу и запоминает итог."""

        try:
            result = service.run_task(
                self.task,
                project=self.project,
                steps=steps,
                policy=policy,
                should_stop=self.should_stop,
            )
            self.result = result
            self.status = "done" if result.get("ok") else "failed"
            self.error = str(result.get("error") or "")
        except Exception as error:  # noqa: BLE001 — статус важнее трейса
            self.status = "failed"
            self.error = f"{type(error).__name__}: {error}"
        finally:
            if self.cancelled or self._stop.is_set():
                self.status = "cancelled"

            self.finished = datetime.now(timezone.utc).isoformat()


class RunRegistry:
    """Память прогонов: не больше MAX_RUNS, старые вытесняются."""

    def __init__(self, limit: int = MAX_RUNS) -> None:
        self.limit = limit
        self._runs: dict[str, RunRecord] = {}
        self._order: list[str] = []
        self._lock = threading.Lock()

    def add(self, record: RunRecord) -> RunRecord:
        """Регистрирует прогон."""

        with self._lock:
            self._runs[record.id] = record
            self._order.append(record.id)

            while len(self._order) > self.limit:
                old = self._order.pop(0)
                self._runs.pop(old, None)

        return record

    def get(self, run_id: str) -> RunRecord | None:
        """Находит прогон по id."""

        return self._runs.get(run_id)

    def cancel(self, run_id: str) -> bool:
        """Отменяет прогон, если он ещё идёт."""

        record = self._runs.get(run_id)

        if record is None:
            return False

        cancelled = record.cancel()
        record.cancelled = cancelled

        return cancelled

    def clear(self) -> None:
        """Очищает реестр (нужно тестам)."""

        with self._lock:
            self._runs.clear()
            self._order.clear()


RUNS = RunRegistry()
