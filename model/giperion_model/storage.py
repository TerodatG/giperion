# GiperionModel/giperion_model/storage.py                             v001
# Атомарная запись чекпоинтов и JSON с одной резервной копией.
# Последнее изменение: первый вариант — temp, fsync, os.replace, .bak.

import json
import os
import shutil
from pathlib import Path

from giperion_model._shared.json_store import path_guard


def _backup(path: Path) -> None:
    """Сохраняет предыдущую версию как .bak."""

    if not path.is_file():
        return

    try:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    except OSError:
        pass


def _replace(temp: Path, target: Path) -> None:
    """Сбрасывает temp на диск и подменяет цель."""

    with temp.open("rb") as file:
        try:
            os.fsync(file.fileno())
        except OSError:
            pass

    _backup(target)
    os.replace(temp, target)


def save_torch(path: Path, payload: dict) -> None:
    """Пишет torch-чекпоинт атомарно и оставляет .bak."""

    import torch

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with path_guard(target):
        temp = target.with_name(target.name + ".tmp")
        torch.save(payload, temp)

        try:
            _replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)


def save_json(path: Path, payload) -> None:
    """Пишет JSON атомарно и оставляет .bak."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with path_guard(target):
        temp = target.with_name(target.name + ".tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        try:
            _replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)


def save_text(path: Path, text: str) -> None:
    """Пишет текст атомарно и оставляет .bak."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with path_guard(target):
        temp = target.with_name(target.name + ".tmp")
        temp.write_text(text, encoding="utf-8")

        try:
            _replace(temp, target)
        finally:
            temp.unlink(missing_ok=True)
