# Giperion/terminal/core/agent/lsp_client.py                           v001
# Минимальный LSP-клиент: JSON-RPC поверх stdio, диагностика и переходы.

import json
import queue
import subprocess
import threading
import time
from pathlib import Path

# Сколько ждать ответа сервера на запрос.
DEFAULT_TIMEOUT = 15.0

# Сколько ждать диагностику после открытия файла.
DIAGNOSTIC_WAIT = 3.0

LANGUAGE_IDS = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".java": "java",
    ".json": "json",
    ".md": "markdown",
}


class LspError(RuntimeError):
    """Ошибка запуска или общения с языковым сервером."""


def file_uri(path: Path) -> str:
    """URI файла для LSP."""

    resolved = Path(path).resolve()

    return resolved.as_uri()


def language_id(path: Path) -> str:
    """Язык файла по расширению."""

    return LANGUAGE_IDS.get(Path(path).suffix.lower(), "plaintext")


class LspClient:
    """Клиент одного языкового сервера."""

    def __init__(
        self,
        command: list[str],
        root: Path,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.command = list(command)
        self.root = Path(root).resolve()
        self.timeout = timeout

        self._process: subprocess.Popen | None = None
        self._messages: queue.Queue = queue.Queue()
        self._next_id = 0
        self._lock = threading.Lock()
        self._opened: dict[str, int] = {}

    # --- Запуск и остановка ---

    def start(self) -> None:
        """Запускает сервер и выполняет initialize."""

        if self._process is not None:
            return

        try:
            self._process = subprocess.Popen(
                self.command,
                cwd=str(self.root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise LspError(
                f"не удалось запустить LSP-сервер: {error}"
            ) from error

        threading.Thread(
            target=self._reader,
            daemon=True,
        ).start()

        self.request(
            "initialize",
            {
                "processId": None,
                "rootUri": self.root.as_uri(),
                "capabilities": {},
            },
        )
        self.notify("initialized", {})

    def stop(self) -> None:
        """Останавливает сервер."""

        process = self._process
        self._process = None

        if process is None:
            return

        try:
            self.request("shutdown", None, timeout=2.0)
            self.notify("exit", None)
        except (LspError, OSError):
            pass

        try:
            process.terminate()
            process.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass

    def __enter__(self) -> "LspClient":
        self.start()

        return self

    def alive(self) -> bool:
        """Жив ли процесс сервера."""

        return (
            self._process is not None
            and self._process.poll() is None
        )

    def __exit__(self, *exc_info) -> None:
        self.stop()

    # --- Транспорт ---

    def _reader(self) -> None:
        """Читает сообщения сервера в очередь."""

        stream = self._process.stdout if self._process else None

        if stream is None:
            return

        while True:
            try:
                length = self._read_headers(stream)
            except (OSError, ValueError):
                break

            if length is None:
                break

            try:
                body = stream.read(length)
            except (OSError, ValueError):
                break

            if not body:
                break

            try:
                self._messages.put(json.loads(body.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue

    @staticmethod
    def _read_headers(stream) -> int | None:
        """Читает заголовки и возвращает длину тела."""

        length = None

        while True:
            line = stream.readline()

            if not line:
                return None

            text = line.decode("ascii", errors="replace").strip()

            if not text:
                return length

            if text.lower().startswith("content-length:"):
                length = int(text.split(":", 1)[1].strip())

    def _send(self, payload: dict) -> None:
        """Пишет сообщение серверу."""

        process = self._process

        if process is None or process.stdin is None:
            raise LspError("LSP-сервер не запущен")

        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")

        with self._lock:
            try:
                process.stdin.write(header + body)
                process.stdin.flush()
            except OSError as error:
                raise LspError(f"канал к LSP закрыт: {error}") from error

    def notify(self, method: str, params) -> None:
        """Отправляет уведомление."""

        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def request(self, method: str, params, timeout: float | None = None) -> dict:
        """Отправляет запрос и ждёт ответ с тем же id."""

        with self._lock:
            self._next_id += 1
            request_id = self._next_id

        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )

        deadline = time.monotonic() + (timeout or self.timeout)

        while True:
            left = deadline - time.monotonic()

            if left <= 0:
                raise LspError(f"LSP не ответил на {method}")

            try:
                message = self._messages.get(timeout=left)
            except queue.Empty as error:
                raise LspError(f"LSP не ответил на {method}") from error

            if message.get("id") == request_id and "method" not in message:
                if "error" in message:
                    raise LspError(
                        f"LSP вернул ошибку: {message['error']}"
                    )

                return message.get("result") or {}

    # --- Документы ---

    def open_document(self, path: Path) -> str:
        """Открывает файл в сервере и возвращает URI."""

        uri = file_uri(path)

        if uri in self._opened:
            return uri

        text = Path(path).read_text(encoding="utf-8", errors="replace")

        self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": language_id(path),
                    "version": 1,
                    "text": text,
                }
            },
        )
        self._opened[uri] = 1

        return uri

    # --- Возможности ---

    def diagnostics(self, path: Path, wait: float = DIAGNOSTIC_WAIT) -> list[dict]:
        """Ждёт диагностику для файла и возвращает её."""

        uri = self.open_document(path)
        deadline = time.monotonic() + wait
        latest: list[dict] = []

        while time.monotonic() < deadline:
            try:
                message = self._messages.get(timeout=0.2)
            except queue.Empty:
                continue

            if message.get("method") != "textDocument/publishDiagnostics":
                continue

            params = message.get("params") or {}

            if params.get("uri") == uri:
                latest = list(params.get("diagnostics") or [])

                break

        return latest

    def definition(self, path: Path, line: int, character: int) -> list[dict]:
        """Переход к определению в позиции (строка и колонка с нуля)."""

        uri = self.open_document(path)

        return _as_list(
            self.request(
                "textDocument/definition",
                {
                    "textDocument": {"uri": uri},
                    "position": {
                        "line": max(0, line - 1),
                        "character": max(0, character - 1),
                    },
                },
            )
        )

    def references(self, path: Path, line: int, character: int) -> list[dict]:
        """Список ссылок на символ в позиции."""

        uri = self.open_document(path)

        return _as_list(
            self.request(
                "textDocument/references",
                {
                    "textDocument": {"uri": uri},
                    "position": {
                        "line": max(0, line - 1),
                        "character": max(0, character - 1),
                    },
                    "context": {"includeDeclaration": True},
                },
            )
        )

    def symbols(self, path: Path) -> list[dict]:
        """Символы файла: функции, классы, методы."""

        uri = self.open_document(path)

        return _as_list(
            self.request(
                "textDocument/documentSymbol",
                {"textDocument": {"uri": uri}},
            )
        )

    def hover(self, path: Path, line: int, character: int) -> dict:
        """Подсказка типа или документация в позиции."""

        uri = self.open_document(path)
        result = self.request(
            "textDocument/hover",
            {
                "textDocument": {"uri": uri},
                "position": {
                    "line": max(0, line - 1),
                    "character": max(0, character - 1),
                },
            },
        )

        return result if isinstance(result, dict) else {}


def _as_list(result) -> list[dict]:
    """Приводит ответ LSP к списку."""

    if isinstance(result, dict):
        return [result]

    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]

    return []
