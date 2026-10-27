# Giperion/tools/browser_scenario.py                                  v001
# Повтор браузерного сценария из JSON: вход, форма, скачивание.
# Последнее изменение: первый вариант — run/save.

import argparse
import json
import sys
from pathlib import Path

from config import BASE_DIR
from terminal.core.agent import browser_js


def load(path: Path) -> dict:
    """Читает сценарий и проверяет поля."""

    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Сценарий не прочитан: {error}") from error

    if not isinstance(document, dict):
        raise ValueError("Сценарий должен быть объектом.")

    if not str(document.get("url") or "").strip():
        raise ValueError("В сценарии нет url.")

    actions = document.get("actions") or []

    if not isinstance(actions, list):
        raise ValueError("actions должен быть массивом.")

    return document


def run(path: Path, root: Path = BASE_DIR) -> dict:
    """Выполняет сценарий и возвращает ответ браузера."""

    document = load(path)
    result = browser_js.act(
        Path(root),
        str(document["url"]),
        actions=document.get("actions") or [],
        wait=str(document.get("wait") or ""),
        shot=bool(document.get("shot")),
        timeout=int(document.get("timeout") or 60),
        full_page=bool(document.get("full_page")),
    )

    return {
        "ok": bool(result.ok),
        "text": result.text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Повторить браузерный сценарий из JSON.",
    )
    parser.add_argument("scenario")
    parser.add_argument("--save", default="")
    parser.add_argument("--root", default=str(BASE_DIR))
    args = parser.parse_args()

    try:
        result = run(
            Path(args.scenario),
            Path(args.root),
        )
    except ValueError as error:
        print("Сценарий не выполнен:", error)

        return 1

    if args.save:
        target = Path(args.save)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("OK" if result["ok"] else "ОШИБКА")
    print(result["text"][:2_000])

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
