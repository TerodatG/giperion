# Giperion/terminal/core/update_rollback.py                            v001
# Откат обновления: вернуть файлы из снимка.

import shutil
from pathlib import Path

from terminal.core.update_types import ApplyResult, UpdateError


def rollback_backup(root: Path, backup: Path | str) -> ApplyResult:
    """Возвращает файлы из снимка обратно в проект."""

    source = Path(backup)

    if not source.is_dir():
        raise UpdateError(f"снимок не найдена: {source}")

    restored: list[str] = []

    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue

        relative = path.relative_to(source)
        destination = Path(root) / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        restored.append(relative.as_posix())

    if not restored:
        raise UpdateError("в снимка нет файлов")

    return ApplyResult(
        version="rollback",
        files=sorted(restored),
        backup_dir=source,
        requires_restart=True,
    )


def last_backup(updates_dir: Path) -> Path | None:
    """Самая свежая снимок в updates/backup."""

    folder = Path(updates_dir) / "backup"

    if not folder.is_dir():
        return None

    items = [item for item in folder.iterdir() if item.is_dir()]

    if not items:
        return None

    return max(items, key=lambda item: item.stat().st_mtime)


def rollback_last(root: Path, updates_dir: Path) -> ApplyResult:
    """Откатывает последнее обновление."""

    backup = last_backup(updates_dir)

    if backup is None:
        raise UpdateError("снимков нет")

    return rollback_backup(root, backup)
