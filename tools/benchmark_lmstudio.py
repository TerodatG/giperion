# Giperion/tools/benchmark_lmstudio.py                               v001
# Прямой замер скорости модели в LM Studio через OpenAI-совместимый API.
# Считает TTFT, время генерации и токены в секунду по usage.

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL = "qwen3-coder-30b"
DEFAULT_PROMPT = (
    "Напиши связный текст примерно на 250–350 слов о том, почему "
    "модульный код проще поддерживать. Пиши обычными абзацами, без "
    "маркированных списков, таблиц и заголовков. Не представляйся."
)


def _request_json(url: str, timeout: int = 10) -> dict:
    """Читает JSON с локального сервера LM Studio."""

    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def list_models(base_url: str) -> list[str]:
    """Список моделей, загруженных в LM Studio."""

    document = _request_json(f"{base_url}/models")

    return [
        str(item.get("id"))
        for item in document.get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]


def _read_stream(response) -> tuple[dict, list[str], float | None, float | None]:
    """Читает SSE и возвращает usage, текст и метки времени."""

    usage: dict = {}
    parts: list[str] = []
    first_token = None
    last_token = None

    for raw_line in response:
        line = raw_line.decode("utf-8", "replace").strip()

        if not line.startswith("data: "):
            continue

        payload = line[6:]

        if payload == "[DONE]":
            break

        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if chunk.get("usage"):
            usage = chunk["usage"]

        choices = chunk.get("choices") or []

        if not choices:
            continue

        delta = choices[0].get("delta") or {}
        text = delta.get("content")

        if not text:
            continue

        now = time.perf_counter()

        if first_token is None:
            first_token = now

        last_token = now
        parts.append(str(text))

    return usage, parts, first_token, last_token


def _speeds(
    total: float,
    ttft: float,
    generation: float,
    completion: int,
) -> tuple[float, float]:
    """Скорость генерации и end-to-end."""

    generation_tps = 0.0

    if generation > 0 and completion > 1:
        generation_tps = (completion - 1) / generation
    elif total > ttft and completion:
        generation_tps = completion / (total - ttft)

    end_to_end = completion / total if total else 0.0

    return generation_tps, end_to_end


def measure(
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
) -> dict:
    """Один потоковый запрос с замером TTFT и генерации."""

    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.perf_counter()

    with urllib.request.urlopen(request, timeout=timeout) as response:
        usage, parts, first_token, last_token = _read_stream(response)

    finished = time.perf_counter()

    ttft = (first_token - started) if first_token is not None else 0.0
    generation = (
        (last_token - first_token)
        if first_token is not None and last_token is not None
        else 0.0
    )
    completion = int(usage.get("completion_tokens", 0) or 0)
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    total = finished - started
    generation_tps, end_to_end = _speeds(
        total,
        ttft,
        generation,
        completion,
    )
    answer = "".join(parts)

    return {
        "ttft": ttft,
        "total": total,
        "generation": generation,
        "prompt": prompt_tokens,
        "completion": completion,
        "generation_tps": generation_tps,
        "end_to_end_tps": end_to_end,
        "chars": len(answer),
        "answer": answer,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Прямой бенчмарк модели LM Studio.",
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=600)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--show-answer", action="store_true")
    args = parser.parse_args()

    try:
        models = list_models(args.url)
    except (OSError, urllib.error.URLError) as error:
        print(f"LM Studio недоступен: {error}")
        return

    if args.model not in models:
        print(f"Модель «{args.model}» не загружена в LM Studio.")
        print("Доступны: " + ", ".join(models))
        return

    print(f"LM Studio: {args.url}")
    print(f"Модель: {args.model}")
    print(f"Запрос: {args.prompt[:90]}…")
    print()

    for index in range(max(0, args.warmup)):
        print(f"Прогрев {index + 1}/{args.warmup}…")

        try:
            measure(
                args.url,
                args.model,
                "Ответь одним словом: да",
                8,
                args.timeout,
            )
        except (OSError, urllib.error.URLError) as error:
            print(f"Ошибка прогрева: {error}")
            return

    results = []

    for index in range(max(1, args.runs)):
        print(f"Замер {index + 1}/{args.runs}…")

        try:
            result = measure(
                args.url,
                args.model,
                args.prompt,
                args.max_tokens,
                args.timeout,
            )
        except (OSError, urllib.error.URLError) as error:
            print(f"Ошибка замера: {error}")
            continue

        results.append(result)

        print(
            f"  TTFT {result['ttft']:.2f} с · "
            f"всего {result['total']:.2f} с · "
            f"output {result['completion']} ток. · "
            f"генерация {result['generation_tps']:.1f} ток/с · "
            f"сквозная {result['end_to_end_tps']:.1f} ток/с"
        )

    if not results:
        print("Нет успешных замеров.")
        return

    print()
    print("Итог:")

    for key, title, unit in (
        ("ttft", "TTFT", "с"),
        ("total", "общее время", "с"),
        ("completion", "output-токены", "ток."),
        ("generation_tps", "скорость генерации", "ток/с"),
        ("end_to_end_tps", "сквозная скорость", "ток/с"),
        ("chars", "символов в ответе", "симв."),
    ):
        values = [item[key] for item in results]
        median = statistics.median(values)
        print(
            f"  {title}: медиана {median:.2f} {unit} "
            f"(мин {min(values):.2f}, макс {max(values):.2f})"
        )

    if args.show_answer:
        print()
        print("Начало ответа:")
        print(results[0]["answer"][:600])


if __name__ == "__main__":
    main()
