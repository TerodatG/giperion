# Giperion/tools/benchmark_model.py                                  v001
# Небольшой замер скорости внешней модели через локальный OpenCode.
# Считает токены в секунду по фактическому usage ответа.

from __future__ import annotations

import argparse
import statistics
import time

from terminal.core.model_registry import (
    DEFAULT_MODEL_ID,
    get_active_model,
    get_current_model_id,
    get_model,
)
from terminal.core.opencode_client import OpenCodeError, ask_model

DEFAULT_MODEL = "go-deepseek-v4.1-flash"
DEFAULT_PROMPT = (
    "Напиши связный текст примерно на 250–350 слов о том, почему "
    "модульный код проще поддерживать. Пиши обычными абзацами, без "
    "маркированных списков, таблиц и заголовков. Не представляйся."
)


def resolve_model(
    value: str,
    provider: str,
) -> tuple[str, str, str]:
    """Возвращает (подпись, model_id, provider_id)."""

    app_model = get_model(value)

    if app_model is not None:
        return (
            app_model["name"],
            app_model["model_id"],
            app_model.get("provider_id") or provider,
        )

    return value, value, provider


def measure(
    model_id: str,
    provider_id: str,
    prompt: str,
    title: str,
    timeout: int,
) -> dict:
    """Один запрос: время, usage и скорость."""

    started = time.perf_counter()
    answer, usage = ask_model(
        model_id,
        prompt,
        provider_id=provider_id,
        title=title,
        timeout=timeout,
    )
    elapsed = time.perf_counter() - started

    output = int(usage.get("output", 0) or 0)
    reasoning = int(usage.get("reasoning", 0) or 0)
    total = int(usage.get("total", 0) or 0)
    input_tokens = int(usage.get("input", 0) or 0)

    return {
        "elapsed": elapsed,
        "input": input_tokens,
        "output": output,
        "reasoning": reasoning,
        "total": total,
        "output_tps": output / elapsed if elapsed else 0.0,
        "total_tps": total / elapsed if elapsed else 0.0,
        "chars": len(answer),
        "answer": answer,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Замер токенов в секунду для модели OpenCode.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="ID модели приложения или OpenCode.",
    )
    parser.add_argument(
        "--provider",
        default="opencode-go",
        help="Provider ID для OpenCode (по умолчанию opencode-go).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=2,
        help="Сколько замеров сделать после прогрева.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Сколько прогревочных запросов сделать.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Таймаут одного запроса, секунд.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Текст запроса.",
    )
    parser.add_argument(
        "--show-answer",
        action="store_true",
        help="Показать начало ответа.",
    )
    args = parser.parse_args()

    model_value = args.model

    if model_value == "active":
        model_value = get_current_model_id()

    active = get_active_model()

    if (
        model_value == DEFAULT_MODEL
        and active is not None
        and active["id"] != DEFAULT_MODEL_ID
    ):
        # По умолчанию мерим активную внешнюю модель, если она выбрана.
        model_value = active["id"]

    label, model_id, provider_id = resolve_model(
        model_value,
        args.provider,
    )

    print(f"Модель: {label}")
    print(f"OpenCode: {provider_id}/{model_id}")
    print(f"Запрос: {args.prompt[:90]}…")
    print()

    for index in range(max(0, args.warmup)):
        print(f"Прогрев {index + 1}/{args.warmup}…")

        try:
            measure(
                model_id,
                provider_id,
                args.prompt,
                f"Бенчмарк · прогрев {index + 1}",
                args.timeout,
            )
        except OpenCodeError as error:
            print(f"Ошибка прогрева: {error}")
            return

    results = []

    for index in range(max(1, args.runs)):
        print(f"Замер {index + 1}/{args.runs}…")

        try:
            result = measure(
                model_id,
                provider_id,
                args.prompt,
                f"Бенчмарк · замер {index + 1}",
                args.timeout,
            )
        except OpenCodeError as error:
            print(f"Ошибка замера: {error}")
            continue

        results.append(result)

        print(
            f"  время {result['elapsed']:.2f} с · "
            f"output {result['output']} ток. · "
            f"reasoning {result['reasoning']} · "
            f"input {result['input']} · "
            f"{result['output_tps']:.1f} ток/с output, "
            f"{result['total_tps']:.1f} ток/с всего"
        )

    if not results:
        print("Нет успешных замеров.")
        return

    print()
    print("Итог:")

    for key, title, unit in (
        ("elapsed", "время", "с"),
        ("output", "output-токены", "ток."),
        ("reasoning", "reasoning-токены", "ток."),
        ("total", "всего токенов", "ток."),
        ("output_tps", "скорость output", "ток/с"),
        ("total_tps", "скорость всего", "ток/с"),
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
