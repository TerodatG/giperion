# Giperion/tools/plugin_catalog.py                                    v001
# Локальный каталог плагинов: список и установка по имени.
# Последнее изменение: первый вариант — JSON-каталог и plugin_install.

import argparse
import json
import sys
from pathlib import Path

from config import DATA_DIR
from tools import plugin_install

CATALOG_FILE = DATA_DIR / "plugin_catalog.json"


def load(path: Path | None = None) -> list[dict]:
    """Читает каталог; битые записи пропускаются."""

    source = Path(path or CATALOG_FILE)

    try:
        document = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    raw = document.get("plugins") if isinstance(document, dict) else None

    if not isinstance(raw, list):
        return []

    result = []

    for item in raw:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name") or "").strip()
        path_text = str(item.get("path") or "").strip()

        if not name or not path_text:
            continue

        result.append(
            {
                "name": name,
                "path": path_text,
                "description": str(item.get("description") or ""),
            }
        )

    return result


def find(name: str, path: Path | None = None) -> dict | None:
    """Запись каталога по имени."""

    needle = str(name or "").strip().lower()

    return next(
        (
            item
            for item in load(path)
            if item["name"].lower() == needle
        ),
        None,
    )


def install(
    name: str,
    path: Path | None = None,
    target: Path = plugin_install.PLUGIN_DIR,
    allow_unsigned: bool = False,
    force: bool = False,
) -> dict:
    """Устанавливает плагин из каталога."""

    source = Path(path or CATALOG_FILE)
    entry = find(name, source)

    if entry is None:
        raise ValueError(f"Плагин «{name}» не найден в каталоге.")

    folder = Path(entry["path"])

    if not folder.is_absolute():
        folder = source.parent / folder

    return plugin_install.install(
        folder,
        target=target,
        force=force,
        allow_unsigned=allow_unsigned,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Локальный каталог плагинов.",
    )
    parser.add_argument("--catalog", default=str(CATALOG_FILE))
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--install", default="")
    parser.add_argument("--target", default=str(plugin_install.PLUGIN_DIR))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-unsigned", action="store_true")
    args = parser.parse_args()
    catalog = Path(args.catalog)

    if args.install:
        try:
            result = install(
                args.install,
                catalog,
                target=Path(args.target),
                allow_unsigned=args.allow_unsigned,
                force=args.force,
            )
        except ValueError as error:
            print("Не установлено:", error)

            return 1

        print(
            f"Установлено: {result['name']} · "
            f"файлов {result['files']}"
        )

        return 0

    plugins = load(catalog)

    if not plugins:
        print("Каталог пуст или не найден:", catalog)

        return 1

    for item in plugins:
        print(f"· {item['name']}: {item['description'] or item['path']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
