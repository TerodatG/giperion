# Giperion/tools/agent_api.py                                          v001
# Локальный HTTP API терминала: health и read-only задачи.
# Последнее изменение: первый вариант — токен, 127.0.0.1, JSON.

import argparse
import json
import secrets
import sys
import threading
import time
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from config import BASE_DIR, DATA_DIR
from terminal.core.agent.loop import run_agent
from terminal.core.agent.redact import redact
from tools.eval_runner import build_brain

TOKEN_FILE = DATA_DIR / "agent_api_token"
CALL_LOG_FILE = DATA_DIR / "agent_api_calls.jsonl"
MAX_BODY = 1_000_000
DEFAULT_PORT = 8765
RATE_LIMIT = 30
RATE_WINDOW = 60.0
_RATE_LOCK = threading.Lock()
_RATE: dict[str, list[float]] = {}
_LOG_LOCK = threading.Lock()


def allow_request(key: str, now: float | None = None) -> bool:
    """Простое окно запросов: не больше RATE_LIMIT в минуту."""

    moment = time.monotonic() if now is None else now
    floor = moment - RATE_WINDOW

    with _RATE_LOCK:
        stamps = [
            stamp for stamp in _RATE.get(key, []) if stamp >= floor
        ]

        if len(stamps) >= RATE_LIMIT:
            _RATE[key] = stamps

            return False

        stamps.append(moment)
        _RATE[key] = stamps

    return True


def project_root(value: str) -> Path | None:
    """Проект API: только подкаталог рабочей папки приложения."""

    text = str(value or "").strip()

    if not text:
        return Path(BASE_DIR).resolve()

    candidate = Path(text)

    if not candidate.is_absolute():
        candidate = Path(BASE_DIR) / candidate

    try:
        resolved = candidate.resolve()
        resolved.relative_to(Path(BASE_DIR).resolve())
    except (OSError, ValueError):
        return None

    if not resolved.is_dir():
        return None

    return resolved


def log_call(
    task: str,
    result: dict,
    elapsed: float,
    root: Path,
    client: str = "",
) -> None:
    """Журнал вызовов API без токена и с редакцией секретов."""

    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "client": client[:64],
        "project": root.name,
        "task": redact(task[:300]).text,
        "ok": bool(result.get("ok")),
        "steps": int(result.get("steps") or 0),
        "elapsed_ms": int(elapsed * 1000),
    }

    try:
        CALL_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        with _LOG_LOCK:
            with CALL_LOG_FILE.open("a", encoding="utf-8") as file:
                file.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _trace(steps: list) -> list[dict]:
    """Короткий трейс шагов для внешнего клиента."""

    trace = []

    for step in steps:
        try:
            item = asdict(step)
        except TypeError:
            item = {
                "index": getattr(step, "index", 0),
                "kind": getattr(step, "kind", ""),
                "title": getattr(step, "title", ""),
                "detail": getattr(step, "detail", ""),
            }

        item["detail"] = str(item.get("detail") or "")[:1_000]
        trace.append(item)

    return trace


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

    try:
        import os

        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass

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


def handle_task(payload: dict, client: str = "") -> dict:
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

    root = project_root(str(payload.get("project") or ""))

    if root is None:
        return {
            "ok": False,
            "error": "Проект вне рабочей папки или не найден.",
        }

    try:
        steps = min(40, max(1, int(payload.get("max_steps") or 5)))
    except (TypeError, ValueError):
        steps = 5

    started = time.monotonic()
    brain, model_name = build_brain("", "")
    result = run_agent(
        task,
        brain,
        root,
        max_steps=steps,
        policy="read",
        approve=None,
        ground_first=True,
    )
    answer = {
        "ok": not result.cancelled and not result.error,
        "model": model_name,
        "project": root.name,
        "answer": result.answer,
        "error": result.error,
        "cancelled": result.cancelled,
        "steps": len(result.steps),
        "trace": _trace(result.steps),
    }
    log_call(
        task,
        answer,
        time.monotonic() - started,
        root,
        client,
    )

    return answer


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

        client = str(self.client_address[0])

        if not allow_request(client):
            self._json(
                429,
                {"ok": False, "error": "too many requests"},
            )

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

        self._json(200, handle_task(payload, client))


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
