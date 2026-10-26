# Giperion/tools/audit_log.py                                         v001
# Проверка и просмотр хеш-цепочки аудита агента.
# Последнее изменение: первый вариант — --check и --tail.

import argparse
import json
import sys

from terminal.core.agent import audit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверить или показать журнал действий агента.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="проверить цепочку хешей (по умолчанию)",
    )
    parser.add_argument(
        "--tail",
        type=int,
        default=0,
        help="показать последние N записей",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.tail:
        entries = audit.tail(args.tail)

        if args.json:
            print(json.dumps(entries, ensure_ascii=False, indent=2))
        else:
            for entry in entries:
                target = entry.get("payload", {}).get("target", "")
                print(
                    f"{entry.get('ts')} · {entry.get('event')} · "
                    f"{target}"
                )

        return 0

    ok, message = audit.verify()

    print(("OK · " if ok else "ОШИБКА · ") + message)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
