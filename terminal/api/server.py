# Giperion/terminal/api/server.py                                      v001
# HTTP-сервер терминала: /health, /version, /tools, /runs, /run.

import hmac
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from terminal.api import config, service
from terminal.core.app_version import current_version

# Пути, доступные без токена: мониторинг живости.
PUBLIC_PATHS = ("/health",)


class ApiHandler(BaseHTTPRequestHandler):
    """Обработчик запросов API."""

    server_version = "GiperionAPI/1.0"
    protocol_version = "HTTP/1.1"

    # --- Маршрутизация ---

    def do_GET(self) -> None:  # noqa: N802 — имя задаёт стандарт
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 — имя задаёт стандарт
        self._dispatch("POST")

    def log_message(self, format: str, *args) -> None:
        """Пишет журнал в stderr, без лишнего шума."""

        sys.stderr.write(
            "%s - %s\n" % (self.address_string(), format % args)
        )

    def _dispatch(self, method: str) -> None:
        """Проверяет токен и вызывает нужный обработчик."""

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path not in PUBLIC_PATHS and not self._authorized():
            self._send(401, {"error": "нужен токен доступа"})

            return

        try:
            if method == "GET" and path == "/health":
                self._send(200, {"ok": True})
            elif method == "GET" and path == "/version":
                self._send(
                    200,
                    {
                        "version": current_version(),
                        "tools": len(service.tools()),
                    },
                )
            elif method == "GET" and path == "/tools":
                self._send(200, {"tools": service.tools()})
            elif method == "GET" and path == "/runs":
                query = parse_qs(parsed.query)
                limit = int((query.get("limit") or ["20"])[0])
                self._send(200, {"runs": service.recent_runs(limit)})
            elif method == "POST" and path == "/run":
                self._handle_run()
            else:
                self._send(404, {"error": "неизвестный путь"})
        except service.ApiError as error:
            self._send(error.status, {"error": str(error)})
        except config.ApiConfigError as error:
            self._send(400, {"error": str(error)})
        except Exception as error:  # noqa: BLE001 — API не должен падать
            self._send(500, {"error": f"{type(error).__name__}: {error}"})

    # --- Обработчики ---

    def _handle_run(self) -> None:
        """Запускает задачу агента по телу запроса."""

        payload = self._read_json()

        if payload is None:
            return

        result = service.run_task(
            task=str(payload.get("task") or ""),
            project=str(payload.get("project") or "."),
            steps=payload.get("steps") or config.DEFAULT_STEPS,
            policy=str(payload.get("policy") or "read"),
        )

        self._send(200, result)

    # --- Служебное ---

    def _authorized(self) -> bool:
        """Сверяет токен из заголовка."""

        expected = config.api_token(create=False)

        if not expected:
            return False

        header = self.headers.get("Authorization", "")

        if header.lower().startswith("bearer "):
            given = header[7:].strip()
        else:
            given = self.headers.get("X-Giperion-Token", "").strip()

        return bool(given) and hmac.compare_digest(given, expected)

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
    print(f"проекты: {', '.join(str(p) for p in config.allowed_roots())}",
          file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("остановлено", file=sys.stderr)
    finally:
        server.server_close()

    return 0
