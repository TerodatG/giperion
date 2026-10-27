# Giperion/tools/agent_api.py                                          v001
# Локальный HTTP API терминала: health и read-only задачи.
# Последнее изменение: первый вариант — токен, 127.0.0.1, JSON.

import argparse
import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from config import BASE_DIR, DATA_DIR
from terminal.core.agent.loop import run_agent
from tools.eval_runner import build_brain

TOKEN_FILE = DATA_DIR / "agent_api_token"
MAX_BODY = 1_000_000
DEFAULT_PORT = 8765


def token() -> str:
    """Токен API: env или файл; файл создаётся при первом обращении."""

    import os

    value = os.environ.get("GIPERION_API_TOKEN", "").strip()

    if value:
        return value

    try:
        stored = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        stored = ""

    if stored:
        return stored

    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    created = secrets.token_hex(24)
    TOKEN_FILE.write_text(created, encoding="utf-8")

    return created


def authorized(header: str) -> bool:
    """Проверяет Bearer-токен."""

    expected = token()
    prefix = "Bearer "

    if not header.startswith(prefix):
        return False

    return secrets.compare_digest(
        header[len(prefix):].strip(),
        expected,
    )


def handle_task(payload: dict) -> dict:
    """Выполняет задачу только на чтение."""

    task = str(payload.get("task") or "").strip()

    if not task:
        return {"ok": False, "error": "Пустая задача."}

    policy = str(payload.get("policy") or "read")

    if policy != "read":
        return {
            "ok": False,
            "error": "API разрешает только policy=read.",
        }

    try:
        steps = min(40, max(1, int(payload.get("max_steps") or 5)))
    except (TypeError, ValueError):
        steps = 5

    brain, model_name = build_brain("", "")
    result = run_agent(
        task,
        brain,
        BASE_DIR,
        max_steps=steps,
        policy="read",
        approve=None,
        ground_first=True,
    )

    return {
        "ok": not result.cancelled and not result.error,
        "model": model_name,
        "answer": result.answer,
        "error": result.error,
        "cancelled": result.cancelled,
        "steps": len(result.steps),
    }


class Handler(BaseHTTPRequestHandler):
    """Минимальный JSON-обработчик."""

    server_version = "GiperionAPI/1.0"

    def log_message(self, fmt, *args) -> None:  # noqa: N802
        pass

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/health":
            self._json(404, {"ok": False, "error": "not found"})

            return

        self._json(200, {"ok": True, "service": "giperion-terminal"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/task":
            self._json(404, {"ok": False, "error": "not found"})

            return

        if not authorized(str(self.headers.get("Authorization") or "")):
            self._json(401, {"ok": False, "error": "bad token"})

            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0

        if length <= 0 or length > MAX_BODY:
            self._json(413, {"ok": False, "error": "bad body size"})

            return

        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "error": "bad json"})

            return

        if not isinstance(payload, dict):
            self._json(400, {"ok": False, "error": "bad json"})

            return

        self._json(200, handle_task(payload))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Локальный API терминала. Только 127.0.0.1, только read-only."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--print-token",
        action="store_true",
        help="напечатать токен и выйти",
    )
    args = parser.parse_args()

    if args.print_token:
        print(token())

        return 0

    server = ThreadingHTTPServer(
        (args.host, args.port),
        Handler,
    )
    print(f"API: http://{args.host}:{args.port}")
    print("Токен:", TOKEN_FILE, "(или GIPERION_API_TOKEN)")
    print("POST /task, GET /health; Ctrl+C — остановить.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Остановлено.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
