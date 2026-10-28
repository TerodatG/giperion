# Giperion/tools/migrate_data.py                                      v001
# Миграции data/: версия схемы, каталоги и резервная копия.
# Последнее изменение: первый вариант — версия и ensure-каталоги.

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from config import DATA_DIR
from tools import backup_data

CURRENT_VERSION = 1
VERSION_FILE = DATA_DIR / "schema_version.json"
DIRECTORIES = (
    "agent_memory",
    "agent_backups",
    "agent_browser",
    "agent_tasks",
    "agent_nightly",
    "agent_eval",
)


def read_version(path: Path | None = None) -> int:
    """Версия схемы данных; нет файла — 0."""

    source = Path(path or VERSION_FILE)

    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    try:
        return max(0, int(document.get("version") or 0))
    except (TypeError, ValueError):
        return 0


def _write_version(version: int, path: Path | None = None) -> None:
    target = Path(path or VERSION_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "version": int(version),
                "updated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def migrate(
    root: Path | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Доводит data/ до CURRENT_VERSION; возвращает шаги."""

    base = Path(root or DATA_DIR)
    version = read_version(base / "schema_version.json")

    if version >= CURRENT_VERSION:
        return [f"уже актуально: v{version}"]

    steps = []

    if not dry_run:
        target = base / "backups" / (
            "pre-migrate-"
            + datetime.now().strftime("%Y%m%d-%H%M%S")
            + ".zip"
        )
        backup_data.create(target=target, with_secrets=True)
        steps.append(f"резервная копия: {target.name}")

    for name in DIRECTORIES:
        folder = base / name

        if not folder.is_dir():
            steps.append(f"каталог: {name}")

            if not dry_run:
                folder.mkdir(parents=True, exist_ok=True)

    steps.append(f"версия: {version} → {CURRENT_VERSION}")

    if not dry_run:
        _write_version(CURRENT_VERSION, base / "schema_version.json")

    return steps


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Миграции data/ с резервной копией.",
    )
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", default="")
    args = parser.parse_args()

    base = Path(args.root) if args.root else None
    version = read_version(
        (base or DATA_DIR) / "schema_version.json"
    )

    if args.check:
        print(f"Версия данных: {version}, актуальная: {CURRENT_VERSION}")

        return 0 if version >= CURRENT_VERSION else 1

    try:
        steps = migrate(base, args.dry_run)
    except (OSError, ValueError) as error:
        print("Миграция не выполнена:", error)

        return 1

    for step in steps:
        print("·", step)

    return 0


if __name__ == "__main__":
    sys.exit(main())
