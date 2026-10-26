# Giperion/terminal/core/agent/embeddings.py                            v001
# Эмбеддинги через OpenAI-совместимый /embeddings локального провайдера.
# Последнее изменение: первый вариант — автопоиск модели и батч-запрос.

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request

from terminal.core.agent import settings

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
MODEL_HINTS = ("embed", "bge", "e5-", "gte-")
DETECT_TTL = 60.0

# Кеш автопоиска: (адрес, ключ) → (когда, модель).
_detected: dict[tuple[str, str], tuple[float, str]] = {}


class EmbeddingError(RuntimeError):
    """Эмбеддинги недоступны или ответ сервера непонятен."""


def is_local_url(url: str) -> bool:
    """Адрес ведёт на эту же машину?"""

    try:
        host = urllib.parse.urlsplit(str(url or "")).hostname
    except ValueError:
        return False

    name = str(host or "").casefold()

    return name in LOCAL_HOSTS or name.endswith(".localhost")


def _json_request(
    url: str,
    api_key: str,
    payload: dict | None,
    timeout: int = 30,
) -> dict:
    """Один запрос JSON; payload=None означает GET."""

    body = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method="POST" if body is not None else "GET",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=max(5, int(timeout)),
        ) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as error:
        raise EmbeddingError(
            f"Сервер эмбеддингов недоступен: {error}"
        ) from error

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise EmbeddingError(
            "Сервер эмбеддингов вернул не JSON."
        ) from error

    if not isinstance(data, dict):
        raise EmbeddingError("Сервер эмбеддингов вернул не объект.")

    return data


def _provider_values() -> dict[str, str]:
    """Адрес и ключ провайдера: файл важнее окружения, поле — по частям."""

    stored = settings.load_settings()
    env = settings.env_provider_values()

    return {
        "base_url": str(stored.get("base_url") or env["base_url"]).strip(),
        "api_key": str(stored.get("api_key") or env["api_key"]).strip(),
    }


def detect_model(base_url: str, api_key: str = "") -> str:
    """Ищет модель эмбеддингов в /models, кешируя результат."""

    base = str(base_url or "").rstrip("/")
    cache_key = (base, api_key)
    now = time.monotonic()
    cached = _detected.get(cache_key)

    if cached is not None and now - cached[0] < DETECT_TTL:
        return cached[1]

    try:
        data = _json_request(base + "/models", api_key, None, timeout=10)
    except EmbeddingError:
        return ""

    models = data.get("data")

    if not isinstance(models, list):
        return ""

    found = ""

    for item in models:
        if not isinstance(item, dict):
            continue

        name = str(item.get("id") or "")

        if any(hint in name.casefold() for hint in MODEL_HINTS):
            found = name
            break

    _detected[cache_key] = (now, found)

    return found


def client() -> tuple[str, str, str] | None:
    """Адрес, ключ и модель эмбеддингов; None — нельзя или не настроено."""

    if not settings.semantic_enabled():
        return None

    values = _provider_values()
    base_url = values["base_url"]

    if not base_url or not is_local_url(base_url):
        return None

    model = settings.embedding_model() or detect_model(
        base_url,
        values["api_key"],
    )

    if not model:
        return None

    return base_url.rstrip("/"), values["api_key"], model


def embed(
    texts: list[str],
    *,
    target: tuple[str, str, str] | None = None,
    timeout: int = 30,
) -> list[list[float]]:
    """Векторы для списка текстов одним запросом."""

    values = [str(text) for text in texts]

    if not values:
        return []

    chat = target or client()

    if chat is None:
        raise EmbeddingError("Эмбеддинги не настроены.")

    base_url, api_key, model = chat
    data = _json_request(
        base_url + "/embeddings",
        api_key,
        {"model": model, "input": values},
        timeout=timeout,
    )

    rows = data.get("data")

    if not isinstance(rows, list) or len(rows) != len(values):
        raise EmbeddingError("Сервер вернул неверное число векторов.")

    vectors: list[list[float]] = []

    try:
        for row in rows:
            vector = row.get("embedding") if isinstance(row, dict) else None

            if not isinstance(vector, list) or not vector:
                raise EmbeddingError("Пустой вектор в ответе.")

            vectors.append([float(value) for value in vector])
    except (TypeError, ValueError) as error:
        raise EmbeddingError("Вектор содержит не числа.") from error

    return vectors


def cosine(left: list[float], right: list[float]) -> float:
    """Косинус между векторами; 0 при нулевой длине."""

    if not left or not right:
        return 0.0

    size = min(len(left), len(right))
    dot = 0.0
    one = 0.0
    two = 0.0

    for index in range(size):
        dot += left[index] * right[index]
        one += left[index] * left[index]
        two += right[index] * right[index]

    if one <= 0.0 or two <= 0.0:
        return 0.0

    return dot / (math.sqrt(one) * math.sqrt(two))
