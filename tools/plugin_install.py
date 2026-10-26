# Giperion/tools/plugin_install.py                                    v001
# Установка плагина инструмента из папки с манифестом.
# Последнее изменение: первый вариант — проверка, хеш, копирование.

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from config import BASE_DIR
from terminal.core.agent.registry_catalog import PLUGIN_PERMISSIONS
from terminal.core.agent.registry_plugins import (
    PLUGIN_DIR,
    PLUGIN_NAME,
)

RISKS = {"read", "write", "exec"}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def validate(
    folder: Path,
) -> tuple[dict, Path, list[Path]]:
    """Проверяет манифест и возвращает его, манифест-файл и модули."""

    base = Path(folder)
    manifests = sorted(base.glob("*.json"))

    if len(manifests) != 1:
        raise ValueError(
            "В папке должен быть ровно один JSON-манифест."
        )

    manifest_path = manifests[0]

    try:
        document = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Манифест не читается: {error}") from error

    if not isinstance(document, dict):
        raise ValueError("Манифест должен быть объектом.")

    name = str(document.get("name") or "").strip()

    if not PLUGIN_NAME.fullmatch(name):
        raise ValueError(f"Недопустимое имя плагина: {name}")

    if not str(document.get("description") or "").strip():
        raise ValueError("У плагина нет описания.")

    risk = str(document.get("risk") or "read")

    if risk not in RISKS:
        raise ValueError(f"Неизвестный risk: {risk}")

    permissions = document.get("permissions")

    if permissions is not None:
        if not isinstance(permissions, list) or not all(
            isinstance(item, str) for item in permissions
        ):
            raise ValueError("permissions должен быть списком строк.")

        unknown = set(permissions) - PLUGIN_PERMISSIONS

        if unknown:
            raise ValueError(
                "Неизвестные разрешения: " + ", ".join(sorted(unknown))
            )

    module_name = str(document.get("module") or "").strip()

    if not module_name.endswith(".py"):
        raise ValueError("module должен указывать на .py.")

    modules = [
        path
        for path in base.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    module = base / module_name

    if not module.is_file():
        raise ValueError(f"Модуль не найден: {module_name}")

    return document, manifest_path, modules


def install(
    folder: Path,
    target: Path = PLUGIN_DIR,
    force: bool = False,
) -> dict:
    """Копирует плагин в data/agent_tools и пишет хеши."""

    document, manifest_path, modules = validate(folder)
    name = str(document["name"])
    destination = Path(target) / name

    if destination.exists() and not force:
        raise ValueError(
            f"Плагин «{name}» уже установлен; используйте --force."
        )

    if destination.exists():
        shutil.rmtree(destination)

    destination.mkdir(parents=True, exist_ok=True)

    hashes = {}

    for path in modules:
        relative = path.relative_to(Path(folder))
        target_path = destination / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target_path)
        hashes[relative.as_posix()] = _hash(target_path)

    document = dict(document)
    document["installed_at"] = datetime.now().isoformat(
        timespec="seconds"
    )
    document["sha256"] = hashes
    (destination / manifest_path.name).write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "name": name,
        "path": destination,
        "files": len(hashes),
        "permissions": document.get("permissions") or [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Установить плагин из папки с JSON-манифестом.",
    )
    parser.add_argument("folder")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--target", default=str(PLUGIN_DIR))
    args = parser.parse_args()

    folder = Path(args.folder)

    try:
        if args.check:
            document, _manifest, modules = validate(folder)
            print(
                f"OK · {document['name']} · модулей {len(modules)} · "
                f"risk={document.get('risk') or 'read'}"
            )
            return 0

        result = install(
            folder,
            target=Path(args.target),
            force=args.force,
        )
    except ValueError as error:
        print("Не установлено:", error)
        return 1

    print(
        f"Установлено: {result['name']} · файлов {result['files']} · "
        f"{result['path']}"
    )
    print(
        "Включите плагины в «Провайдере» и проверьте манифест; "
        f"относительно проекта: "
        f"{result['path'].relative_to(BASE_DIR).as_posix()}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
