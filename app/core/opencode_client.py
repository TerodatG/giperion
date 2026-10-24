# Giperion/app/core/opencode_client.py                              v001
# Канал связи с локальным сервисом OpenCode: бесплатные внешние модели.
# Пароль берётся из service.json, адрес — из `opencode-cli service status`.

import base64
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from config import BASE_DIR

# Сколько ждём обычные запросы и ответ модели.
REQUEST_TIMEOUT = 20
ANSWER_TIMEOUT = 180

_SERVICE = {"url": "", "password": ""}


class OpenCodeError(RuntimeError):
    """Сервис OpenCode недоступен или ответил ошибкой."""


def _config_file() -> Path:
    """Путь к service.json OpenCode с паролем локального сервиса."""

    config_home = os.environ.get("XDG_CONFIG_HOME")

    if config_home:
        return Path(config_home) / "opencode" / "service.json"

    return Path.home() / ".config" / "opencode" / "service.json"


def _read_password() -> str:
    """Читает пароль сервиса. Сам пароль в журналы не попадает."""

    if _SERVICE["password"]:
        return _SERVICE["password"]

    path = _config_file()

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OpenCodeError(
            "Не читается service.json OpenCode. "
            "Запусти OpenCode и попробуй снова."
        ) from error

    password = document.get("password")

    if not isinstance(password, str) or not password:
        raise OpenCodeError(
            "В service.json OpenCode нет пароля сервиса."
        )

    _SERVICE["password"] = password

    return password


def _find_cli() -> str:
    """Ищет opencode-cli: сначала в PATH, потом в установке приложения."""

    for name in ("opencode-cli", "opencode"):
        found = shutil.which(name)

        if found:
            return found

    appdata = os.environ.get("APPDATA")

    if appdata:
        root = Path(appdata) / "ai.opencode.desktop" / "cli"

        if root.is_dir():
            candidates = sorted(
                root.glob("*/opencode-cli.exe"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )

            if candidates:
                return str(candidates[0])

    raise OpenCodeError(
        "Не найден opencode-cli.exe. Запусти OpenCode."
    )


def _discover_url() -> str:
    """Узнаёт адрес локального сервиса через `opencode-cli service status`."""

    if _SERVICE["url"]:
        return _SERVICE["url"]

    command = [_find_cli(), "service", "status"]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise OpenCodeError(
            "Не удалось запустить opencode-cli."
        ) from error

    for token in result.stdout.split():
        if token.startswith("http://") or token.startswith("https://"):
            _SERVICE["url"] = token.rstrip("/")

            return _SERVICE["url"]

    detail = (result.stdout or result.stderr).strip()[:200]

    raise OpenCodeError(
        f"Сервис OpenCode не отвечает. {detail}".strip()
    )


def _headers() -> dict:
    """Заголовки запроса: Basic-авторизация локального сервиса."""

    token = base64.b64encode(
        f"opencode:{_read_password()}".encode("utf-8")
    ).decode("ascii")

    return {
        "Authorization": "Basic " + token,
        "Content-Type": "application/json",
    }


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    timeout: int = REQUEST_TIMEOUT,
    retry: bool = True,
) -> dict:
    """Выполняет запрос к API OpenCode и возвращает JSON."""

    url = _discover_url()

    data = (
        json.dumps(body, ensure_ascii=False).encode("utf-8")
        if body is not None
        else None
    )

    request = urllib.request.Request(
        url + path,
        data=data,
        method=method,
        headers=_headers(),
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]

        raise OpenCodeError(
            f"OpenCode ответил {error.code}: {detail}"
        ) from error
    except (urllib.error.URLError, TimeoutError) as error:
        if retry:
            # Сервис мог перезапуститься на другом порту — ищем заново.
            _SERVICE["url"] = ""

            return _request(
                method,
                path,
                body,
                timeout,
                retry=False,
            )

        raise OpenCodeError(
            "Сервис OpenCode недоступен. Проверь, "
            "что приложение OpenCode запущено."
        ) from error

    if not raw.strip():
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError as error:
        raise OpenCodeError(
            "OpenCode вернул не JSON."
        ) from error


def extract_answer(messages: dict) -> tuple[str, dict]:
    """Достаёт последний ответ модели и расход токенов из переписки."""

    assistants = [
        message
        for message in messages.get("data", [])
        if message.get("type") == "assistant"
    ]

    if not assistants:
        raise OpenCodeError("Модель не вернула ответ.")

    assistant = max(
        assistants,
        key=lambda message: message.get("time", {}).get(
            "created",
            0,
        ),
    )

    error = assistant.get("error")

    if isinstance(error, dict) and error:
        detail = error.get("message") or error.get("type") or "ошибка"

        raise OpenCodeError(f"Модель сообщила об ошибке: {detail}")

    texts = [
        part.get("text", "").strip()
        for part in assistant.get("content", [])
        if part.get("type") == "text"
    ]

    answer = "\n\n".join(text for text in texts if text).strip()

    if not answer:
        raise OpenCodeError("Модель ответила пусто.")

    tokens = assistant.get("tokens") or {}

    usage = {
        "input": int(tokens.get("input", 0) or 0),
        "output": int(tokens.get("output", 0) or 0),
        "reasoning": int(tokens.get("reasoning", 0) or 0),
    }
    usage["total"] = (
        usage["input"] + usage["output"] + usage["reasoning"]
    )

    return answer, usage


def ask_model(
    model_id: str,
    text: str,
    provider_id: str = "opencode",
    title: str = "Гиперион",
    timeout: int = ANSWER_TIMEOUT,
) -> tuple[str, dict]:
    """Спрашивает внешнюю модель через локальный сервис OpenCode.

    Создаёт одноразовую сессию в папке проекта, ждёт ответ и убирает
    сессию, чтобы не засорять список диалогов OpenCode.
    """

    if not model_id:
        raise OpenCodeError("У модели не указан идентификатор OpenCode.")

    session = _request(
        "POST",
        "/api/session",
        {
            "title": title,
            "model": {
                "id": model_id,
                "providerID": provider_id,
            },
            "location": {"directory": str(BASE_DIR)},
        },
    )

    session_id = session.get("data", {}).get("id")

    if not session_id:
        raise OpenCodeError("OpenCode не создал сессию.")

    try:
        _request(
            "POST",
            f"/api/session/{session_id}/prompt",
            {"text": text},
        )
        _request(
            "POST",
            f"/api/experimental/session/{session_id}/wait",
            {},
            timeout=timeout,
        )
        messages = _request(
            "GET",
            f"/api/session/{session_id}/message?limit=30",
        )
    finally:
        try:
            _request(
                "DELETE",
                f"/api/session/{session_id}",
                timeout=10,
            )
        except OpenCodeError:
            # Уборка сессии не должна скрывать настоящую ошибку.
            pass

    return extract_answer(messages)
