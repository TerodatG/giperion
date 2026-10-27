# Giperion/terminal/core/agent/browser_session.py                      v001
# Долгоживущая сессия Chromium: один браузер на задачу.
# Последнее изменение: первый вариант — JSON-протокол и thread-local.

import atexit
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

from config import BASE_DIR

WORKER = "terminal.core.agent.browser_worker"
ENV_KEYS = (
    "PATH",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
)


class BrowserSessionError(RuntimeError):
    """Сессия браузера не запустилась или закрылась."""


def _env() -> dict[str, str]:
    env = {
        key: os.environ[key]
        for key in ENV_KEYS
        if key in os.environ
    }
    env["PYTHONPATH"] = str(BASE_DIR)
    env["PYTHONIOENCODING"] = "utf-8"

    return env


class BrowserSession:
    """Один процесс Chromium с JSON-строками stdin/stdout."""

    def __init__(self, root: Path = BASE_DIR) -> None:
        self.root = Path(root)
        self.process: subprocess.Popen | None = None
        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._next_id = 0

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return

        try:
            self.process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    WORKER,
                    "--serve",
                ],
                cwd=str(self.root),
                env=_env(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
        except OSError as error:
            raise BrowserSessionError(
                f"Сессия браузера не запустилась: {error}"
            ) from error

        self._queue = queue.Queue()
        threading.Thread(
            target=self._read_loop,
            daemon=True,
        ).start()

    def _read_loop(self) -> None:
        stream = self.process.stdout if self.process else None

        if stream is None:
            self._queue.put(None)

            return

        try:
            for line in stream:
                self._queue.put(line)
        except (OSError, ValueError):
            pass
        finally:
            self._queue.put(None)

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def request(
        self,
        command: str,
        timeout: int = 90,
        **params,
    ) -> dict:
        """Отправляет команду и ждёт ответ с тем же id."""

        with self._lock:
            self.start()

            if self.process is None or self.process.stdin is None:
                raise BrowserSessionError("Сессия браузера не запущена.")

            self._next_id += 1
            request_id = self._next_id
            payload = {
                "id": request_id,
                "cmd": command,
                **params,
            }

            try:
                self.process.stdin.write(
                    json.dumps(payload, ensure_ascii=False) + "\n"
                )
                self.process.stdin.flush()
            except (OSError, ValueError) as error:
                raise BrowserSessionError(
                    f"Не удалось отправить команду: {error}"
                ) from error

            while True:
                try:
                    line = self._queue.get(timeout=timeout + 20)
                except queue.Empty as error:
                    raise BrowserSessionError(
                        f"Браузер не ответил за {timeout + 20} с."
                    ) from error

                if line is None:
                    raise BrowserSessionError(
                        "Сессия браузера закрылась."
                    )

                text = str(line).strip()

                if not text:
                    continue

                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue

                if data.get("id") != request_id:
                    continue

                if not data.get("ok"):
                    raise BrowserSessionError(
                        str(data.get("error") or "ошибка браузера")
                    )

                return data

    def close(self) -> None:
        process = self.process
        self.process = None

        if process is None:
            return

        try:
            if process.stdin is not None:
                process.stdin.write(
                    json.dumps({"cmd": "close", "id": -1}) + "\n"
                )
                process.stdin.flush()
        except (OSError, ValueError):
            pass

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()

        try:
            if process.stdin is not None:
                process.stdin.close()
        except OSError:
            pass


_LOCAL = threading.local()
_SESSIONS: list[BrowserSession] = []
_POOL: dict[str, BrowserSession] = {}
_REGISTRY_LOCK = threading.Lock()


def _key(root: Path) -> str:
    return str(Path(root).resolve()).casefold()


def current(root: Path = BASE_DIR) -> BrowserSession:
    """Сессия текущего потока: из пула или новая."""

    session = getattr(_LOCAL, "session", None)

    if session is not None and session.alive():
        return session

    key = _key(root)

    with _REGISTRY_LOCK:
        pooled = _POOL.pop(key, None)

    if pooled is not None and pooled.alive():
        session = pooled
    else:
        session = BrowserSession(root)

        with _REGISTRY_LOCK:
            _SESSIONS.append(session)

    _LOCAL.session = session

    return session


def release_current() -> None:
    """Возвращает живую сессию в пул для следующей задачи."""

    session = getattr(_LOCAL, "session", None)

    if session is None:
        return

    _LOCAL.session = None

    if not session.alive():
        return

    with _REGISTRY_LOCK:
        _POOL[_key(session.root)] = session


def close_current() -> None:
    session = getattr(_LOCAL, "session", None)
    key = _key(session.root) if session is not None else ""

    if session is not None:
        session.close()
        _LOCAL.session = None

    if not key:
        return

    with _REGISTRY_LOCK:
        pooled = _POOL.pop(key, None)

    if pooled is not None:
        pooled.close()


def close_all() -> None:
    """Закрывает все сессии (выход из приложения)."""

    with _REGISTRY_LOCK:
        sessions = list(_SESSIONS)
        sessions.extend(_POOL.values())
        _SESSIONS.clear()
        _POOL.clear()

    for session in sessions:
        session.close()

    if hasattr(_LOCAL, "session"):
        _LOCAL.session = None


atexit.register(close_all)
