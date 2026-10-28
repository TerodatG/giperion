# Giperion/tools/eval_ab.py                                           v001
# A/B-прогон одной задачи на двух моделях.
# Последнее изменение: первый вариант — compare и CLI.

import argparse
import json
import sys

from config import BASE_DIR
from terminal.core.agent.ab import compare
from tools.eval_runner import build_brain


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Сравнить две модели на одной задаче.",
    )
    parser.add_argument("task")
    parser.add_argument("--a-model", default="")
    parser.add_argument("--b-model", default="")
    parser.add_argument("--a-provider", default="")
    parser.add_argument("--b-provider", default="")
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    brain_a, name_a = build_brain(args.a_model, args.a_provider)
    brain_b, name_b = build_brain(args.b_model, args.b_provider)
    result = compare(
        args.task,
        brain_a,
        brain_b,
        BASE_DIR,
        max_steps=max(1, args.steps),
    )
    result["models"] = {"a": name_a, "b": name_b}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))

        return 0

    for side in ("a", "b"):
        item = result[side]
        print(
            f"{side.upper()} · {result['models'][side]} · "
            f"{'OK' if item['ok'] else 'ОШИБКА'} · "
            f"шагов {item['steps']} · токенов {item['tokens']} · "
            f"${item['cost']:.4f}"
        )
        print("  ", (item["answer"] or item["error"] or "—")[:300])

    return 0


if __name__ == "__main__":
    sys.exit(main())
