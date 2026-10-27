# Giperion/terminal/core/agent/plugins.py                              v001
# Установленные плагины: манифесты, разрешения и отзыв.
# Последнее изменение: первый вариант — list_installed/revoke.

import json
import shutil
from pathlib import Path

from config import DATA_DIR

PLUGIN_DIR = DATA_DIR / "agent_tools"


def _manifest(path: Path) -> dict | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    return document if isinstance(document, dict) else None


def list_installed(folder: Path | None = None) -> list[dict]:
    """Плагины с манифестом, разрешениями и папкой."""

    base = Path(folder or PLUGIN_DIR)

    if not base.is_dir():
        return []

    result = []

    for path in sorted(base.glob("*/*.json")):
        if path.name == "signature.json":
            continue

        document = _manifest(path)

        if document is None or not document.get("name"):
            continue

        permissions = document.get("permissions")
        result.append(
            {
                "name": str(document["name"]),
                "description": str(document.get("description") or ""),
                "risk": str(document.get("risk") or "read"),
                "permissions": [
                    str(item)
                    for item in permissions
                    if isinstance(item, str)
                ]
                if isinstance(permissions, list)
                else [],
                "folder": str(path.parent),
            }
        )

    return result


def revoke(name: str, folder: Path | None = None) -> bool:
    """Удаляет папку плагина; только внутри agent_tools."""

    base = Path(folder or PLUGIN_DIR).resolve()
    wanted = str(name or "").strip().lower()

    if not wanted:
        raise ValueError("Не указано имя плагина.")

    for item in list_installed(base):
        if item["name"].lower() != wanted:
            continue

        target = Path(item["folder"]).resolve()

        try:
            target.relative_to(base)
        except ValueError as error:
            raise ValueError("Папка плагина вне agent_tools.") from error

        shutil.rmtree(target)

        return True

    return False
