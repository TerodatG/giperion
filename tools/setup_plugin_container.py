# Giperion/tools/setup_plugin_container.py                            v001
# Подготовка песочницы AppContainer для плагинов агента.
# Последнее изменение: проверка, подготовка и удаление.

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import BASE_DIR
from terminal.core.agent import container

PROBE_NAME = ".giperion_container_probe"


def isolation_check() -> str:
    """Проверяет, что контейнер не читает домашнюю папку пользователя."""

    probe = Path.home() / PROBE_NAME

    try:
        probe.write_text("секрет", encoding="utf-8")
    except OSError as error:
        return f"не удалось создать пробу: {error}"

    script = (
        "from pathlib import Path\n"
        "try:\n"
        f"    Path(r'{probe}').read_text(encoding='utf-8')\n"
        "    print('READ')\n"
        "except Exception:\n"
        "    print('BLOCKED')\n"
    )

    try:
        code, output = container.run_text(
            ["-c", script],
            cwd=BASE_DIR,
            timeout=20,
        )
    finally:
        probe.unlink(missing_ok=True)

    if code != 0:
        return f"контейнер не ответил (код {code}): {output[:120]}"

    return "заблокировано" if "BLOCKED" in output else "ПРОЧИТАЛ (плохо)"


def show_status() -> None:
    status = container.status()

    print("=== Песочница плагинов ===")
    print("платформа:", status["platform"])
    print("профиль:", status["profile"])
    print("python:", status["python"])
    print("готово:", "да" if status["ready"] else "нет")

    if not status["ready"]:
        print(
            "\nПодготовить: python -m tools.setup_plugin_container "
            "--prepare"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AppContainer для плагинов агента.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="показать состояние (по умолчанию)",
    )
    parser.add_argument(
        "--prepare",
        action="store_true",
        help="скопировать Python и выдать права",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="перекопировать Python заново",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="удалить профиль, копию Python и права",
    )
    parser.add_argument(
        "--no-isolation-check",
        action="store_true",
        help="не проверять чтение домашней папки",
    )
    args = parser.parse_args()

    if args.remove:
        for step in container.remove():
            print("·", step)

        return

    if args.prepare:
        try:
            steps = container.prepare(force=args.force)
        except container.ContainerError as error:
            print("Ошибка:", error)
            raise SystemExit(1) from error

        for step in steps:
            print("·", step)

        if not args.no_isolation_check:
            print("· изоляция:", isolation_check())

        show_status()

        return

    show_status()


if __name__ == "__main__":
    main()
