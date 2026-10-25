# Giperion/terminal/core/agent/rollback.py                             v001
# Откат прогона агента: возврат файлов из резервных копий.
# Последнее изменение: первый вариант — по списку файлов и времени.

from datetime import datetime, timedelta
from pathlib import Path

from terminal.core.agent import tools

STAMP_FORMAT = "%Y%m%d-%H%M%S-%f"
STAMP_LENGTH = 22
TOLERANCE = timedelta(seconds=1)


def backup_folder(root: Path) -> Path:
    """Папка резервных копий внутри проекта."""

    return Path(root).resolve() / tools.BACKUP_DIR


def parse_backup_name(name: str) -> tuple[datetime, str] | None:
    """Разбирает имя вида «20261025-182731-163825-src__a.py»."""

    text = str(name or "")

    if len(text) <= STAMP_LENGTH + 1:
        return None

    stamp = text[:STAMP_LENGTH]
    rest = text[STAMP_LENGTH + 1:]

    try:
        moment = datetime.strptime(stamp, STAMP_FORMAT)
    except ValueError:
        return None

    if not rest:
        return None

    return moment, rest.replace("__", "/")


def _parse_moment(value: object) -> datetime | None:
    """Время из записи журнала или настроек."""

    text = str(value or "").strip()

    if not text:
        return None

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def find_backup(
    root: Path,
    relative: str,
    after: datetime | None,
    before: datetime | None,
) -> Path | None:
    """Самая свежая копия файла в промежутке времени прогона."""

    folder = backup_folder(root)

    if not folder.is_dir():
        return None

    wanted = relative.replace("/", "__")
    best: tuple[datetime, Path] | None = None

    for path in folder.glob("*-" + wanted):
        parsed = parse_backup_name(path.name)

        if parsed is None:
            continue

        moment, restored = parsed

        if restored != relative:
            continue

        if after is not None and moment < after:
            continue

        if before is not None and moment > before:
            continue

        if best is None or moment > best[0]:
            best = (moment, path)

    return best[1] if best else None


def plan_rollback(root: Path, record: dict) -> list[dict]:
    """Что можно вернуть для этого прогона: файл и его копия."""

    base = Path(root).resolve()
    started = _parse_moment(record.get("started_at"))
    finished = _parse_moment(record.get("created_at"))

    if started is not None:
        started -= TOLERANCE

    if finished is not None:
        finished += TOLERANCE

    files = record.get("files")

    if not isinstance(files, list):
        return []

    plan = []

    for item in files:
        relative = str(item or "").strip()

        if not relative:
            continue

        backup = find_backup(base, relative, started, finished)

        plan.append(
            {
                "path": relative,
                "backup": backup,
                "current": (base / relative).exists(),
            }
        )

    return plan


def rollback_run(root: Path, record: dict) -> list[str]:
    """Возвращает файлы прогона к состоянию из резервных копий."""

    base = Path(root).resolve()
    lines: list[str] = []

    for item in plan_rollback(base, record):
        relative = item["path"]
        backup = item["backup"]

        if backup is None:
            lines.append(f"{relative}: копия не найдена — пропущено")
            continue

        try:
            target = tools.safe_path(base, relative)
            target.write_bytes(Path(backup).read_bytes())
        except Exception as error:  # noqa: BLE001 — отчёт по каждому файлу
            lines.append(f"{relative}: ошибка — {error}")
            continue

        lines.append(f"{relative}: восстановлен")

    return lines


def can_rollback(record: dict) -> bool:
    """Есть ли у записи журнала файлы для отката."""

    files = record.get("files")

    return isinstance(files, list) and bool(files)
