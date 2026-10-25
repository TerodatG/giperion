# Giperion/terminal/core/agent/watch.py                               v001
# Наблюдатель за файлами проекта: снимки, различия и опрос.
# Последнее изменение: первый вариант — polling, debounce и cooldown.

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from config import DATA_DIR
from shared.storage.json_store import read_json_object, write_json
from terminal.core.agent import tools

SETTINGS_FILE = DATA_DIR / "agent_watch.json"

IGNORED_DIRS = set(tools.SKIP_DIRS) | {
    ".agent_worktrees",
    "data",
    "assets",
}

MAX_CHANGES = 20


@dataclass
class Changes:
    """Что изменилось между двумя снимками."""

    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.added or self.modified or self.deleted)

    def merge(self, other: "Changes") -> None:
        """Сливает изменения, сохраняя уникальность путей."""

        for name, items in (
            ("added", other.added),
            ("modified", other.modified),
            ("deleted", other.deleted),
        ):
            target = getattr(self, name)

            for item in items:
                if item not in target:
                    target.append(item)

    def summary(self) -> str:
        """Короткое описание для журнала и задачи."""

        parts = []

        if self.added:
            parts.append("новые: " + ", ".join(self.added[:5]))

        if self.modified:
            parts.append("изменены: " + ", ".join(self.modified[:5]))

        if self.deleted:
            parts.append("удалены: " + ", ".join(self.deleted[:5]))

        return "\n".join(parts) or "изменений нет"

    def total(self) -> int:
        return len(self.added) + len(self.modified) + len(self.deleted)


def is_ignored(relative: str) -> bool:
    """Служебные папки и файлы не наблюдаются."""

    parts = Path(relative).parts

    if any(part in IGNORED_DIRS for part in parts[:-1]):
        return True

    name = parts[-1] if parts else ""

    return name.startswith(".") or name.endswith(".agent-tmp")


def snapshot(root: Path, limit: int = 50_000) -> dict[str, tuple[int, int]]:
    """Снимок файлов проекта: путь → (mtime_ns, размер)."""

    base = Path(root).resolve()
    result: dict[str, tuple[int, int]] = {}

    for folder, dirnames, filenames in os.walk(base):
        dirnames[:] = [
            name for name in dirnames if name not in IGNORED_DIRS
        ]

        for name in filenames:
            path = Path(folder) / name
            relative = path.relative_to(base).as_posix()

            if is_ignored(relative):
                continue

            try:
                stat = path.stat()
            except OSError:
                continue

            if stat.st_size > 2_000_000:
                continue

            result[relative] = (stat.st_mtime_ns, stat.st_size)

            if len(result) >= limit:
                return result

    return result


def diff(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> Changes:
    """Различия двух снимков с ограничением на длину списков."""

    changes = Changes()

    for path, stamp in after.items():
        old = before.get(path)

        if old is None:
            changes.added.append(path)
        elif old != stamp:
            changes.modified.append(path)

    for path in before:
        if path not in after:
            changes.deleted.append(path)

    changes.added.sort()
    changes.modified.sort()
    changes.deleted.sort()

    changes.added = changes.added[:MAX_CHANGES]
    changes.modified = changes.modified[:MAX_CHANGES]
    changes.deleted = changes.deleted[:MAX_CHANGES]

    return changes


@dataclass(frozen=True)
class WatchSettings:
    """Настройки наблюдателя из data/agent_watch.json."""

    enabled: bool = False
    interval_s: float = 5.0
    debounce_s: float = 3.0
    cooldown_s: float = 20.0
    task: str = (
        "В проекте изменились файлы. Посмотри, что изменилось, и коротко "
        "скажи, всё ли в порядке."
    )
    auto_run: bool = False


def load_settings() -> WatchSettings:
    """Читает настройки наблюдателя, подрезая значения."""

    document = read_json_object(SETTINGS_FILE)

    def number(key: str, default: float, low: float, high: float) -> float:
        try:
            value = float(document.get(key, default))
        except (TypeError, ValueError):
            return default

        return min(high, max(low, value))

    task = str(document.get("task") or "").strip()

    return WatchSettings(
        enabled=document.get("enabled") is True,
        interval_s=number("interval_s", 5.0, 1.0, 120.0),
        debounce_s=number("debounce_s", 3.0, 0.0, 60.0),
        cooldown_s=number("cooldown_s", 20.0, 0.0, 600.0),
        task=task or WatchSettings.task,
        auto_run=document.get("auto_run") is True,
    )


def save_settings(settings: WatchSettings) -> None:
    """Сохраняет настройки наблюдателя."""

    write_json(
        SETTINGS_FILE,
        {
            "enabled": bool(settings.enabled),
            "interval_s": float(settings.interval_s),
            "debounce_s": float(settings.debounce_s),
            "cooldown_s": float(settings.cooldown_s),
            "task": str(settings.task),
            "auto_run": bool(settings.auto_run),
        },
    )


class Watcher:
    """Опрашивает проект и сообщает об изменениях после паузы."""

    def __init__(
        self,
        root: Path,
        interval_s: float = 5.0,
        debounce_s: float = 3.0,
        cooldown_s: float = 20.0,
    ) -> None:
        self.root = Path(root).resolve()
        self.interval_s = max(0.05, float(interval_s))
        self.debounce_s = max(0.0, float(debounce_s))
        self.cooldown_s = max(0.0, float(cooldown_s))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        on_change,
        on_error=None,
        initial: bool = True,
    ) -> None:
        """Запускает опрос в отдельном потоке."""

        if self.running:
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            args=(on_change, on_error),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Останавливает опрос."""

        self._stop.set()

        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _loop(self, on_change, on_error) -> None:
        try:
            baseline = snapshot(self.root)
        except Exception as error:  # noqa: BLE001 — сообщим и выйдем
            if on_error is not None:
                on_error(error)

            return

        pending = Changes()
        last_change = 0.0
        cooldown_until = 0.0

        while not self._stop.wait(self.interval_s):
            try:
                current = snapshot(self.root)
            except Exception as error:  # noqa: BLE001 — переживём один сбой
                if on_error is not None:
                    on_error(error)

                continue

            if time.monotonic() < cooldown_until:
                baseline = current

                continue

            delta = diff(baseline, current)

            if delta:
                pending.merge(delta)
                baseline = current
                last_change = time.monotonic()

            if not pending:
                continue

            if time.monotonic() - last_change < self.debounce_s:
                continue

            changes = pending
            pending = Changes()
            cooldown_until = time.monotonic() + self.cooldown_s
            baseline = snapshot(self.root)

            try:
                on_change(changes)
            except Exception as error:  # noqa: BLE001 — наблюдатель живёт
                if on_error is not None:
                    on_error(error)
