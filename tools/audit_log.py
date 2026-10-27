# Giperion/tools/audit_log.py                                         v002
# Проверка, просмотр, поиск и подписанный экспорт аудита.
# Последнее изменение: экспорт HMAC, поиск и --limit.

import argparse
import json
import sys
from pathlib import Path

from terminal.core.agent import audit


def _print(entries: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return

    for entry in entries:
        target = entry.get("payload", {}).get("target", "")
        print(
            f"{entry.get('ts')} · {entry.get('event')} · {target}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверить, показать, найти или выгрузить аудит.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="проверить цепочку хешей (по умолчанию)",
    )
    parser.add_argument("--tail", type=int, default=0)
    parser.add_argument("--search", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--export",
        default="",
        help="экспортировать журнал в файл",
    )
    parser.add_argument("--key", default="")
    parser.add_argument("--since", default="")
    parser.add_argument("--until", default="")
    parser.add_argument(
        "--prune",
        type=int,
        default=0,
        help="перенести записи старше N дней в архив",
    )
    parser.add_argument(
        "--verify-export",
        default="",
        help="проверить подпись экспортированного файла",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.prune:
        moved = audit.prune(args.prune)
        print(f"Архивировано записей: {moved}")
        ok, message = audit.verify()
        print(("OK · " if ok else "ОШИБКА · ") + message)

        return 0 if ok else 1

    if args.verify_export:
        ok, message = audit.verify_export(
            Path(args.verify_export),
            key_file=Path(args.key) if args.key else None,
        )

        print(("OK · " if ok else "ОШИБКА · ") + message)

        return 0 if ok else 1

    if args.export:
        try:
            target, signature = audit.export(
                Path(args.export),
                key_file=Path(args.key) if args.key else None,
                since=args.since,
                until=args.until,
            )
        except ValueError as error:
            print("Не выгружено:", error)

            return 1

        ok, message = audit.verify_export(
            target,
            signature,
            key_file=Path(args.key) if args.key else None,
        )
        print("Экспорт:", target)
        print("Подпись:", signature)
        print(("OK · " if ok else "ОШИБКА · ") + message)

        return 0 if ok else 1

    if args.search:
        _print(
            audit.search(args.search, args.limit),
            args.json,
        )

        return 0

    if args.tail:
        _print(audit.tail(args.tail), args.json)

        return 0

    ok, message = audit.verify()

    print(("OK · " if ok else "ОШИБКА · ") + message)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
