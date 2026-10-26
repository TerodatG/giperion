# Giperion/tools/agent_daemon.py                                      v001
# Демон расписания: проверяет due и запускает read-only задачи.
# Последнее изменение: первый вариант — интервал, once и subprocess.

import argparse
import subprocess
import sys
import time

from config import BASE_DIR
from terminal.core import schedule


def run_due(limit: int = 2) -> int:
    """Запускает tools.agent_schedule run-due отдельным процессом."""

    try:
        done = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.agent_schedule",
                "run-due",
                "--limit",
                str(max(1, int(limit))),
            ],
            cwd=str(BASE_DIR),
            capture_output=False,
            timeout=3600,
        )

        return int(done.returncode)
    except (OSError, subprocess.TimeoutExpired) as error:
        print("Демон: запуск не удался:", error)

        return 1


def tick(limit: int = 2) -> bool:
    """Один цикл: были ли задачи и запустились ли они."""

    if not schedule.due():
        return False

    run_due(limit)

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Проверяет расписание каждые N секунд и запускает due-задачи. "
            "Только read-only; для остановки — Ctrl+C."
        ),
    )
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.once:
        tick(args.limit)

        return 0

    print(
        f"Демон расписания: интервал {args.interval} с, "
        f"до {args.limit} задач за цикл."
    )

    try:
        while True:
            tick(args.limit)
            time.sleep(max(10, int(args.interval)))
    except KeyboardInterrupt:
        print("Демон остановлен.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
