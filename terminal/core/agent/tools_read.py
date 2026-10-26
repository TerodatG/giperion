# Giperion/terminal/core/agent/tools_read.py                           v001
# Чтение и поиск по файлам проекта.
# Последнее изменение: вынесено из tools.

import os
import shutil
import subprocess
from pathlib import Path

from terminal.core.agent.protocol import ToolResult
from terminal.core.agent.tools_policy import (
    MAX_LIST_ENTRIES,
    MAX_READ_BYTES,
    MAX_READ_CHARS,
    MAX_SEARCH_FILE_BYTES,
    MAX_SEARCH_FILES,
    MAX_SEARCH_HITS,
    SKIP_DIRS,
    TEXT_SUFFIXES,
    ToolError,
    _root,
    safe_path,
)


def list_dir(root: Path, path: str = ".") -> ToolResult:
    """Показывает содержимое папки проекта."""

    try:
        folder = safe_path(root, path)
    except ToolError as error:
        return ToolResult(False, str(error))

    if not folder.exists():
        return ToolResult(False, f"Папка не найдена: {path}")

    if not folder.is_dir():
        return ToolResult(False, f"Это не папка: {path}")

    base = _root(root)
    entries = []

    for item in sorted(
        folder.iterdir(),
        key=lambda entry: (not entry.is_dir(), entry.name.lower()),
    ):
        try:
            safe_path(root, str(item))
        except ToolError:
            continue

        relative = item.relative_to(base).as_posix()

        if item.is_dir():
            entries.append(f"{relative}/")
        else:
            entries.append(relative)

        if len(entries) >= MAX_LIST_ENTRIES:
            entries.append("… список обрезан")
            break

    if not entries:
        return ToolResult(True, "Папка пуста.")

    return ToolResult(True, "\n".join(entries))


def read_file(
    root: Path,
    path: str,
    start: int = 1,
    limit: int = 0,
) -> ToolResult:
    """Читает текстовый файл проекта или диапазон строк.

    `start` — первая строка (с 1), `limit` — сколько вернуть; ноль
    означает «до конца файла».
    """

    try:
        file_path = safe_path(root, path)
    except ToolError as error:
        return ToolResult(False, str(error))

    if not file_path.exists():
        return ToolResult(False, f"Файл не найден: {path}")

    if not file_path.is_file():
        return ToolResult(False, f"Это не файл: {path}")

    try:
        size = file_path.stat().st_size
    except OSError as error:
        return ToolResult(False, f"Не удалось прочитать: {error}")

    if size > MAX_READ_BYTES:
        return ToolResult(
            False,
            f"Файл больше {MAX_READ_BYTES} байт — читай частями.",
        )

    try:
        data = file_path.read_bytes()
    except OSError as error:
        return ToolResult(False, f"Не удалось прочитать: {error}")

    if b"\x00" in data[:4096]:
        return ToolResult(False, "Это двоичный файл, читать не буду.")

    text = data.decode("utf-8", "replace")
    all_lines = text.splitlines()

    try:
        first = max(1, int(start or 1))
    except (TypeError, ValueError):
        first = 1

    try:
        count = max(0, int(limit or 0))
    except (TypeError, ValueError):
        count = 0

    total = len(all_lines)

    if first > 1 or count:
        end = total if count == 0 else min(total, first + count - 1)
        selected = all_lines[first - 1:end]

        if not selected:
            return ToolResult(
                False,
                f"{path}: строки {first}–{end} вне файла "
                f"(всего {total}).",
            )

        text = "\n".join(selected)
        header = (
            f"{path} · строки {first}–{first + len(selected) - 1} "
            f"из {total}\n"
        )
    else:
        header = f"{path} · {total} строк\n"

    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS]
        text += "\n… файл обрезан по лимиту."

    return ToolResult(True, header + text)


def _iter_text_files(base: Path):
    """Перебирает текстовые файлы проекта для поиска без ripgrep."""

    seen = 0

    for folder, dirnames, filenames in os.walk(base):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in SKIP_DIRS
        ]

        for name in filenames:
            path = Path(folder) / name

            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue

            try:
                safe_path(base, str(path))
            except ToolError:
                continue

            try:
                if path.stat().st_size > MAX_SEARCH_FILE_BYTES:
                    continue
            except OSError:
                continue

            seen += 1

            if seen > MAX_SEARCH_FILES:
                return

            yield path


def _search_with_python(
    base: Path,
    query: str,
    folder: Path,
) -> list[str]:
    """Ищет подстроку в текстовых файлах без внешних программ."""

    needle = query.lower()
    hits = []
    paths = (
        [folder]
        if folder.is_file()
        else _iter_text_files(folder)
    )

    for path in paths:
        try:
            relative = path.relative_to(base)

            if (
                folder.is_dir()
                and folder != base
                and folder not in path.parents
            ):
                continue

            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue

            text = path.read_text(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue

        for number, line in enumerate(text.splitlines(), start=1):
            if needle not in line.lower():
                continue

            hits.append(
                f"{relative.as_posix()}:{number}: {line.strip()[:200]}"
            )

            if len(hits) >= MAX_SEARCH_HITS:
                return hits

    return hits


def _search_with_rg(
    base: Path,
    query: str,
    folder: Path,
) -> list[str] | None:
    """Пробует ripgrep; None означает «rg недоступен»."""

    if shutil.which("rg") is None:
        return None

    try:
        result = subprocess.run(
            [
                "rg",
                "-n",
                "--no-heading",
                "--color",
                "never",
                "-i",
                "-m",
                "3",
                "--",
                query,
                str(folder),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    hits = []

    for line in result.stdout.splitlines():
        if not line.strip():
            continue

        parts = line.split(":", 2)

        if len(parts) != 3:
            continue

        raw_path, number, text = parts

        try:
            relative = Path(raw_path).resolve().relative_to(base)
        except ValueError:
            continue

        hits.append(
            f"{relative.as_posix()}:{number}: {text.strip()[:200]}"
        )

        if len(hits) >= MAX_SEARCH_HITS:
            break

    return hits


def search_text(
    root: Path,
    query: str,
    path: str = ".",
) -> ToolResult:
    """Ищет строку по файлам проекта и возвращает совпадения."""

    text = str(query or "").strip()

    if len(text) < 2:
        return ToolResult(False, "Запрос слишком короткий (минимум 2 символа).")

    try:
        folder = safe_path(root, path)
    except ToolError as error:
        return ToolResult(False, str(error))

    if not folder.exists():
        return ToolResult(False, f"Папка не найдена: {path}")

    base = _root(root)

    hits = _search_with_rg(base, text, folder) if folder.is_dir() else None

    if hits is None:
        hits = _search_with_python(
            base,
            text,
            folder,
        )

    if not hits:
        return ToolResult(True, "Совпадений нет.")

    return ToolResult(True, "\n".join(hits))


def _read_text(path: Path) -> str:
    """Читает текстовый файл или объясняет, почему нельзя."""

    data = path.read_bytes()

    if b"\x00" in data[:4096]:
        raise ToolError("Это двоичный файл, менять его нельзя.")

    return data.decode("utf-8", "replace")

