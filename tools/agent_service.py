# Giperion/tools/agent_service.py                                      v001
# Служба Windows для демона расписания: install/remove/query/start/stop.
# Последнее изменение: первый вариант — sc.exe и dry-run.

import argparse
import subprocess
import sys

SERVICE_NAME = "GiperionAgentDaemon"
SERVICE_TITLE = "Giperion Agent Daemon"


def command_for(
    interval: int = 300,
    python: str | None = None,
) -> list[str]:
    """Команда создания службы через sc.exe."""

    exe = str(python or sys.executable)
    bin_path = (
        f'"{exe}" -m tools.agent_daemon --interval '
        f"{max(10, int(interval))}"
    )

    return [
        "sc",
        "create",
        SERVICE_NAME,
        f"binPath= {bin_path}",
        "start=",
        "auto",
        "DisplayName=",
        SERVICE_TITLE,
    ]


def _run(command: list[str]) -> tuple[int, str]:
    try:
        done = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)

    return int(done.returncode), (
        (done.stdout or "") + (done.stderr or "")
    ).strip()


def install(
    interval: int = 300,
    dry_run: bool = False,
) -> tuple[int, str]:
    """Создаёт службу (нужны права администратора)."""

    command = command_for(interval)

    if dry_run:
        return 0, " ".join(command)

    return _run(command)


def remove(dry_run: bool = False) -> tuple[int, str]:
    """Удаляет службу."""

    command = ["sc", "delete", SERVICE_NAME]

    if dry_run:
        return 0, " ".join(command)

    return _run(command)


def control(action: str, dry_run: bool = False) -> tuple[int, str]:
    """start/stop/query."""

    if action not in ("start", "stop", "query"):
        raise ValueError(f"Неизвестное действие: {action}")

    command = ["sc", action, SERVICE_NAME]

    if dry_run:
        return 0, " ".join(command)

    return _run(command)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Служба Windows для демона Giperion.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true")
    group.add_argument("--remove", action="store_true")
    group.add_argument("--start", action="store_true")
    group.add_argument("--stop", action="store_true")
    group.add_argument("--query", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if sys.platform != "win32" and not args.dry_run:
        print("Служба доступна только на Windows.")

        return 1

    if args.install:
        code, output = install(args.interval, args.dry_run)
    elif args.remove:
        code, output = remove(args.dry_run)
    elif args.start:
        code, output = control("start", args.dry_run)
    elif args.stop:
        code, output = control("stop", args.dry_run)
    else:
        code, output = control("query", args.dry_run)

    print(output or f"код {code}")

    return 0 if code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
