# Giperion/terminal/core/agent/summary.py                             v001
# Сводка изменений задачи: файлы, добавленные и удалённые строки, диффы.
# Последнее изменение: первый вариант — по резервным копиям прогона.

import difflib
from pathlib import Path

from terminal.core.agent.rollback import plan_rollback
from terminal.core.agent import tools

MAX_DIFF_LINES = 120
MAX_TOTAL_DIFF = 4000


def _read(path: Path) -> str:
    """Текст файла с защитой от двоичных данных."""

    try:
        data = path.read_bytes()
    except OSError:
        return ""

    if b"\x00" in data[:4096]:
        return ""

    return data.decode("utf-8", "replace")


def _counts(diff_lines: list[str]) -> tuple[int, int]:
    """Сколько строк добавлено и удалено (без заголовков)."""

    added = 0
    removed = 0

    for line in diff_lines:
        if line.startswith("+++") or line.startswith("---"):
            continue

        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1

    return added, removed


def describe_file(root: Path, item: dict) -> dict:
    """Описание одного файла: дифф до состояния из копии."""

    base = Path(root).resolve()
    relative = str(item.get("path") or "")
    backup = item.get("backup")
    target = base / relative

    current = _read(target)
    before = _read(Path(backup)) if backup is not None else ""

    if backup is None:
        return {
            "path": relative,
            "available": False,
            "added": 0,
            "removed": 0,
            "diff": "",
            "note": "копия не найдена",
        }

    diff_lines = list(
        difflib.unified_diff(
            before.splitlines(),
            current.splitlines(),
            fromfile="a/" + relative,
            tofile="b/" + relative,
            lineterm="",
        )
    )

    added, removed = _counts(diff_lines)
    text = "\n".join(diff_lines[:MAX_DIFF_LINES])

    if len(diff_lines) > MAX_DIFF_LINES:
        text += "\n… дифф обрезан"

    return {
        "path": relative,
        "available": True,
        "added": added,
        "removed": removed,
        "diff": text,
        "note": "",
    }


def changes_of(root: Path, record: dict) -> list[dict]:
    """Список изменений прогона по его записи журнала."""

    base = Path(root).resolve()

    return [
        describe_file(base, item)
        for item in plan_rollback(base, record)
    ]


def format_changes(items: list[dict], with_diff: bool = True) -> str:
    """Текст сводки для трейса и окна."""

    if not items:
        return "Изменённых файлов нет."

    added = sum(int(item.get("added") or 0) for item in items)
    removed = sum(int(item.get("removed") or 0) for item in items)

    lines = [
        f"Изменено файлов: {len(items)} (+{added} −{removed})",
    ]

    for item in items:
        sign = (
            f"(+{item['added']} −{item['removed']})"
            if item.get("available")
            else f"({item.get('note') or 'нет копии'})"
        )
        lines.append(f"  {item['path']} {sign}")

    if not with_diff:
        return "\n".join(lines)

    budget = MAX_TOTAL_DIFF

    for item in items:
        diff = str(item.get("diff") or "")

        if not diff:
            continue

        if budget <= 0:
            lines.append("… часть диффов не показана")
            break

        chunk = diff[:budget]
        budget -= len(chunk)
        lines.append("")
        lines.append(chunk)

    return "\n".join(lines)
