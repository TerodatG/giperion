# Giperion/terminal/core/agent/tools_write.py                          v001
# Точечная запись, резервные копии и патчи.
# Последнее изменение: вынесено из tools.

import difflib
import os
import shutil
from datetime import datetime
from pathlib import Path

from shared.action_log import add_action
from terminal.core.agent.protocol import ToolResult
from terminal.core.agent.tools_policy import (
    BACKUP_DIR,
    DIFF_LIMIT,
    MAX_WRITE_CHARS,
    TEXT_SUFFIXES,
    ToolError,
    _root,
    safe_path,
)
from terminal.core.agent.tools_read import _read_text


def _diff(path: str, old: str, new: str) -> str:
    """Собирает унифицированный дифф с ограничением размера."""

    diff = difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile="a/" + path,
        tofile="b/" + path,
        lineterm="",
    )
    text = "\n".join(diff).strip()

    if not text:
        return "Изменений нет."

    if len(text) > DIFF_LIMIT:
        return text[:DIFF_LIMIT] + "\n… дифф обрезан."

    return text


def _backup(root: Path, path: Path) -> str:
    """Кладёт копию файла перед изменением и возвращает её путь."""

    base = _root(root)
    relative = path.relative_to(base)
    folder = base / BACKUP_DIR
    folder.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    name = stamp + "-" + relative.as_posix().replace("/", "__")
    target = folder / name
    shutil.copy2(path, target)

    return target.relative_to(base).as_posix()


def _write_atomic(path: Path, text: str) -> None:
    """Пишет через временный файл, чтобы не оставить половину.

    Пишем байтами: текстовый режим на Windows превращает каждый «\\n» в
    «\\r\\n», и в файле с CRLF после правки появлялись лишние пустые
    строки.
    """

    temp = path.with_name(path.name + ".agent-tmp")
    temp.write_bytes(str(text).encode("utf-8"))

    try:
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(_root(root)).as_posix()


def prepare_write(
    root: Path,
    path: str,
    content: str,
) -> tuple[Path, str, str]:
    """Готовит запись файла: путь, старый текст и дифф."""

    target = safe_path(root, path)

    if target.exists() and not target.is_file():
        raise ToolError("Это не файл.")

    if not target.parent.exists():
        raise ToolError("Папки для файла нет — сначала создай её.")

    if target.suffix.lower() not in TEXT_SUFFIXES:
        raise ToolError("Это не текстовый файл проекта.")

    new_text = str(content)

    if len(new_text) > MAX_WRITE_CHARS:
        raise ToolError("Слишком большой текст для записи.")

    old_text = _read_text(target) if target.exists() else ""
    diff = _diff(_relative(root, target), old_text, new_text)

    return target, old_text, diff


def write_file(root: Path, path: str, content: str) -> ToolResult:
    """Создаёт или полностью перезаписывает текстовый файл."""

    try:
        target, old_text, diff = prepare_write(root, path, content)
    except ToolError as error:
        return ToolResult(False, str(error))

    backup = _backup(root, target) if target.exists() else ""

    _write_atomic(target, str(content))
    add_action(f"Агент: записан файл {_relative(root, target)}")

    header = (
        f"Записан {_relative(root, target)}"
        + (f" · резервная копия {backup}" if backup else " · новый файл")
    )

    return ToolResult(True, header + "\n" + diff)


def _edge_newlines(value: str, at_start: bool) -> int:
    """Сколько переводов строк идёт подряд с края строки."""

    sequence = value if at_start else reversed(value)
    count = 0

    for char in sequence:
        if char in "\r\n":
            count += 1
            continue

        break

    return count


def _trim_insert(old: str, new: str) -> str:
    """Убирает лишние пустые строки по краям вставки.

    Модели часто добавляют перевод строки в начале или конце нового
    фрагмента, хотя в оригинале его не было. Без этого файл расползается
    пустыми строками после каждой правки.
    """

    head = _edge_newlines(new, True) - _edge_newlines(old, True)

    if head > 0:
        new = new[head:]

    tail = _edge_newlines(new, False) - _edge_newlines(old, False)

    if tail > 0:
        new = new[:-tail]

    return new


def prepare_patch(
    root: Path,
    path: str,
    old: str,
    new: str,
) -> tuple[Path, str, str, str]:
    """Готовит точечную замену: путь, старый текст, новый и дифф."""

    if not str(old):
        raise ToolError("Пустой фрагмент для замены.")

    target = safe_path(root, path)

    if not target.exists() or not target.is_file():
        raise ToolError("Файл не найден.")

    text = _read_text(target)
    base_text, base_old, base_new = text, old, new
    count = text.count(old)

    # Модель почти всегда присылает фрагменты с LF, а файлы на Windows
    # хранятся с CRLF. Сравниваем ещё и в единых переводах строк.
    if count == 0:
        unified = text.replace("\r\n", "\n")
        unified_old = old.replace("\r\n", "\n")

        if unified_old:
            count = unified.count(unified_old)

            if count:
                base_text = unified
                base_old = unified_old
                base_new = new.replace("\r\n", "\n")

    if count == 0:
        raise ToolError("Фрагмент не найден в файле — прочитай его заново.")

    if count > 1:
        raise ToolError(
            f"Фрагмент встречается {count} раз — нужен уникальный."
        )

    base_new = _trim_insert(base_old, base_new)
    new_text = base_text.replace(base_old, base_new, 1)

    if base_text is not text and "\r\n" in text:
        new_text = new_text.replace("\n", "\r\n")

    diff = _diff(_relative(root, target), text, new_text)

    return target, text, new_text, diff


def apply_patch(
    root: Path,
    path: str,
    old: str,
    new: str,
) -> ToolResult:
    """Заменяет один уникальный фрагмент в файле."""

    try:
        target, _old, new_text, diff = prepare_patch(
            root,
            path,
            old,
            new,
        )
    except ToolError as error:
        return ToolResult(False, str(error))

    backup = _backup(root, target)
    _write_atomic(target, new_text)
    add_action(f"Агент: правка файла {_relative(root, target)}")

    return ToolResult(
        True,
        f"Изменён {_relative(root, target)} · копия {backup}\n{diff}",
    )

