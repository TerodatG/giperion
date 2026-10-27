# Giperion/tools/agent_alerts.py                                      v001
# Проверка последних прогонов и вебхук при падении успеха.
# Последнее изменение: первый вариант — summary, порог и notify.

import argparse
import sys

from terminal.core.agent import alerts
from terminal.core.agent.runs import read_runs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверить успех последних прогонов и отправить алерт.",
    )
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--webhook", default="")
    parser.add_argument("--fail", action="store_true")
    args = parser.parse_args()

    runs = read_runs(max(1, args.window))
    stats, alert = alerts.check(
        runs,
        threshold=max(0.0, min(1.0, args.threshold)),
        window=args.window,
        url=args.webhook,
    )

    print(
        f"Прогонов: {stats['total']} · успех {stats['ok']} · "
        f"падений {stats['failed']} · доля {stats['rate']:.0%}"
    )

    if stats["last_error"]:
        print("Последняя ошибка:", stats["last_error"][:300])

    if alert:
        print("АЛЕРТ: успех ниже порога; вебхук отправлен, если задан.")

    return 2 if args.fail and alert else 0


if __name__ == "__main__":
    sys.exit(main())
