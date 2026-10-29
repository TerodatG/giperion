# Giperion/terminal/api/server.py                                      v002
# HTTP-сервер терминала: прогоны, отмена, журнал вызовов и лимит частоты.

import hmac
import json
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from terminal.api import api_config as config
from terminal.api import runs, service
from terminal.core.app_version import current_version

# Пути, доступные без токена: мониторинг живости.
PUBLIC_PATHS = ("/health",)

# Лимит частоты: не больше N запросов за окно (секунд) на токен.
RATE_WINDOW = 60.0
RATE_LIMIT = 60

_RATE: dict[str, list[float]] = {}
_RATE_LOCK = threading.Lock()


def _allowed(token: str) -> bool:
    """Простое скользящее окно по токену."""

    now = time.monotonic()

    with _RATE_LOCK:
        stamps = [item for item in _RATE.get(token, []) if now - item < RATE_WINDOW]
        stamps.append(now)
        _RATE[token] = stamps

        return len(stamps) <= RATE_LIMIT


def _journal(entry: dict) -> None:
    """Дописывает строку в журнал вызовов."""

    try:
        config.JOURNAL.parent.mkdir(parents=True, exist_ok=True)

        with config.JOURNAL.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


class ApiHandler(BaseHTTPRequestHandler):
    """Обработчик запросов API."""

    server_version = "GiperionAPI/1.1"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 — имя задаёт стандарт
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 — имя задаёт стандарт
        self._dispatch("POST")

    def log_message(self, format: str, *args) -> None:
        """Пишет журнал в stderr, без лишнего шума."""

        sys.stderr.write(
            "%s - %s\n" % (self.address_string(), format % args)
        )

    # --- Маршрутизация ---

    def _dispatch(self, method: str) -> None:
        """Проверяет токен, лимит и вызывает обработчик."""

        started = time.monotonic()
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        token = self._token()
        status = 500

        try:
            if path not in PUBLIC_PATHS:
                if not self._authorized(token):
                    status = 401
                    self._send(401, {"error": "нужен токен доступа"})

                    return

                if not _allowed(token):
                    status = 429
                    self._send(429, {"error": "слишком много запросов"})

                    return

            status = self._route(method, path, parsed)
        except service.ApiError as error:
            status = error.status
            self._send(error.status, {"error": str(error)})
        except config.ApiConfigError as error:
            status = 400
            self._send(400, {"error": str(error)})
        except Exception as error:  # noqa: BLE001 — API не должен падать
            status = 500
            self._send(500, {"error": f"{type(error).__name__}: {error}"})
        finally:
            _journal(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "method": method,
                    "path": path,
                    "status": status,
                    "ms": int((time.monotonic() - started) * 1000),
                }
            )

    def _route(self, method: str, path: str, parsed) -> int:
        """Разбирает путь и возвращает код ответа."""

        if method == "GET" and path == "/health":
            self._send(200, {"ok": True})

            return 200

        if method == "GET" and path == "/version":
            self._send(
                200,
                {"version": current_version(), "tools": len(service.tools())},
            )

            return 200

        if method == "GET" and path == "/tools":
            self._send(200, {"tools": service.tools()})

            return 200

        if method == "GET" and path == "/runs":
            query = parse_qs(parsed.query)
            limit = int((query.get("limit") or ["20"])[0])
            self._send(200, {"runs": service.recent_runs(limit)})

            return 200

        if path.startswith("/run/"):
            return self._route_run(method, path)

        if method == "POST" and path == "/run":
            return self._handle_run()

        self._send(404, {"error": "неизвестный путь"})

        return 404

    def _route_run(self, method: str, path: str) -> int:
        """GET /run/{id} и POST /run/{id}/cancel."""

        parts = path.strip("/").split("/")
        run_id = parts[1] if len(parts) > 1 else ""
        action = parts[2] if len(parts) > 2 else ""

        if method == "GET" and not action:
            record = runs.RUNS.get(run_id)

            if record is None:
                self._send(404, {"error": "прогон не найден"})

                return 404

            self._send(200, record.payload())

            return 200

        if method == "POST" and action == "cancel":
            if not runs.RUNS.cancel(run_id):
                self._send(409, {"error": "прогон уже завершён"})

                return 409

            self._send(202, {"id": run_id, "status": "cancelling"})

            return 202

        self._send(404, {"error": "неизвестный путь"})

        return 404

    # --- Запуск ---

    def _handle_run(self) -> int:
        """Запускает задачу: сразу или в фоне."""

        payload = self._read_json()

        if payload is None:
            return 400

        task = str(payload.get("task") or "")
        project = str(payload.get("project") or ".")
        steps = payload.get("steps") or config.DEFAULT_STEPS
        policy = str(payload.get("policy") or "read")
        wait = bool(payload.get("wait", True))

        if not wait:
            record = runs.RUNS.add(runs.RunRecord(task, project))
            record.start(steps, policy)
            self._send(202, {"id": record.id, "status": record.status})

            return 202

        result = service.run_task(
            task=task,
            project=project,
            steps=steps,
            policy=policy,
        )
        self._send(200, result)

        return 200

    # --- Служебное ---

    def _token(self) -> str:
        """Токен из заголовка."""

        header = self.headers.get("Authorization", "")

        if header.lower().startswith("bearer "):
            return header[7:].strip()

        return self.headers.get("X-Giperion-Token", "").strip()

    def _authorized(self, given: str) -> bool:
        """Сверяет токен с ожидаемым."""

        expected = config.api_token(create=False)

        if not expected or not given:
            return False

        return hmac.compare_digest(given, expected)

    def _read_json(self) -> dict | None:
        """Читает JSON-тело с ограничением размера."""

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._send(400, {"error": "неверный Content-Length"})

            return None

        if length <= 0:
            self._send(400, {"error": "пустое тело запроса"})

            return None

        if length > config.MAX_BODY_BYTES:
            self._send(413, {"error": "тело запроса слишком велико"})

            return None

        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, {"error": "тело должно быть JSON"})

            return None

        if not isinstance(payload, dict):
            self._send(400, {"error": "ожидался JSON-объект"})

            return None

        return payload

    def _send(self, status: int, payload: dict) -> None:
        """Отправляет JSON-ответ."""

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(host: str = "", port: int | None = None) -> ThreadingHTTPServer:
    """Создаёт сервер (порт 0 — свободный)."""

    bind_port = config.api_port() if port is None else port

    return ThreadingHTTPServer(
        (host or config.api_host(), bind_port),
        ApiHandler,
    )


def serve(host: str = "", port: int | None = None) -> int:
    """Запускает сервер до Ctrl+C."""

    token = config.api_token()

    server = make_server(host, port)
    actual = server.server_address

    print(
        f"Giperion API: http://{actual[0]}:{actual[1]}",
        file=sys.stderr,
    )
    print(f"токен: {token}", file=sys.stderr)
    print(
        f"проекты: {', '.join(str(p) for p in config.allowed_roots())}",
        file=sys.stderr,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("остановлено", file=sys.stderr)
    finally:
        server.server_close()

    return 0
