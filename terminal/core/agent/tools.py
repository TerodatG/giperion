# Giperion/terminal/core/agent/tools.py                             v001
# Read-only инструменты агента: список, чтение и поиск по проекту.
# Последнее изменение: первый вариант — только чтение, без записи.

import os
import shutil
import subprocess
import sys
import difflib
from datetime import datetime
from pathlib import Path

from shared.action_log import add_action
from terminal.core.agent.commands import CommandError, validate_command
from terminal.core.agent.protocol import ToolResult

MAX_LIST_ENTRIES = 200
MAX_READ_CHARS = 20000
MAX_READ_BYTES = 1_000_000
MAX_SEARCH_HITS = 40
MAX_SEARCH_FILE_BYTES = 512_000
MAX_SEARCH_FILES = 3000
MAX_WRITE_CHARS = 200_000
DIFF_LIMIT = 6000
TEST_TIMEOUT = 300
BACKUP_DIR = "data/agent_backups"

TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".jsonc", ".ui", ".txt", ".toml", ".cfg",
    ".ini", ".ps1", ".bat", ".cmd", ".yml", ".yaml", ".html", ".css",
    ".js", ".ts", ".csv",
}

SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "env", "node_modules",
    ".pytest_cache", "logs", "archive", "models", ".mypy_cache",
}

DENIED_NAMES = {
    ".env", "service.json", "auth.json", "credentials.json",
    "id_rsa", "id_ed25519",
}

DENIED_SUFFIXES = (".pem", ".key", ".pfx", ".p12")

DENIED_RELATIVE = {
    "data/conversations.json",
    "data/conversations_before_model_tags.json",
    "data/user_profile.json",
}

DENIED_PREFIXES = (
    "archive",
    "logs",
    "data/chat_contexts",
)


class ToolError(RuntimeError):
    """Инструмент отказал: путь, аргумент или лимит."""


def _root(root: Path) -> Path:
    """Возвращает разрешённый корень проекта."""

    return Path(root).resolve()


def safe_path(root: Path, raw: str) -> Path:
    """Проверяет путь: только внутри проекта и без секретов."""

    base = _root(root)
    text = str(raw or ".").strip()

    if not text:
        text = "."

    candidate = Path(text)

    if not candidate.is_absolute():
        candidate = base / candidate

    resolved = candidate.resolve()

    try:
        relative = resolved.relative_to(base)
    except ValueError as error:
        raise ToolError(
            "Путь вне рабочей папки проекта запрещён."
        ) from error

    parts = relative.as_posix()

    if ".git" in relative.parts:
        raise ToolError("Служебная папка .git агенту недоступна.")

    if relative.name in DENIED_NAMES:
        raise ToolError("Этот файл закрыт для агента.")

    if relative.suffix.lower() in DENIED_SUFFIXES:
        raise ToolError("Файлы ключей закрыты для агента.")

    if parts in DENIED_RELATIVE:
        raise ToolError("Личные данные пользователя закрыты.")

    if any(
        parts == prefix or parts.startswith(prefix + "/")
        for prefix in DENIED_PREFIXES
    ):
        raise ToolError("Архивы, журналы и контексты чатов закрыты.")

    return resolved


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


def read_file(root: Path, path: str) -> ToolResult:
    """Читает текстовый файл проекта с ограничениями."""

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
    lines = text.count("\n") + 1

    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS]
        text += "\n… файл обрезан по лимиту."

    header = f"{path} · {lines} строк\n"

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
    paths = [folder] if folder.is_file() else _iter_text_files(base)

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
            folder if folder.is_dir() else folder.parent,
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
    """Пишет через временный файл, чтобы не оставить половину."""

    temp = path.with_name(path.name + ".agent-tmp")
    temp.write_text(text, encoding="utf-8")

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


def prepare_patch(
    root: Path,
    path: str,
    old: str,
    new: str,
) -> tuple[Path, str, str]:
    """Готовит точечную замену: путь, новый текст и дифф."""

    if not str(old):
        raise ToolError("Пустой фрагмент для замены.")

    target = safe_path(root, path)

    if not target.exists() or not target.is_file():
        raise ToolError("Файл не найден.")

    text = _read_text(target)
    count = text.count(old)

    if count == 0:
        raise ToolError("Фрагмент не найден в файле — прочитай его заново.")

    if count > 1:
        raise ToolError(
            f"Фрагмент встречается {count} раз — нужен уникальный."
        )

    new_text = text.replace(old, new, 1)
    diff = _diff(_relative(root, target), text, new_text)

    return target, new_text, diff


def apply_patch(
    root: Path,
    path: str,
    old: str,
    new: str,
) -> ToolResult:
    """Заменяет один уникальный фрагмент в файле."""

    try:
        target, new_text, diff = prepare_patch(
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


def run_tests(root: Path) -> ToolResult:
    """Запускает pytest в папке проекта и отдаёт хвост вывода."""

    base = _root(root)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=base,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEST_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            False,
            f"Тесты не успели за {TEST_TIMEOUT} секунд.",
        )
    except OSError as error:
        return ToolResult(False, f"Не удалось запустить тесты: {error}")

    output = (result.stdout + result.stderr).strip()
    tail = output[-4000:] if output else "вывод пуст"
    ok = result.returncode == 0

    add_action(
        "Агент: pytest, код "
        f"{result.returncode}"
    )

    return ToolResult(
        ok,
        f"pytest: код {result.returncode}\n{tail}",
    )


def run_command(root: Path, command: str) -> ToolResult:
    """Выполняет команду из белого списка без shell."""

    try:
        tokens = validate_command(command)
    except CommandError as error:
        return ToolResult(False, str(error))

    base = _root(root)

    try:
        result = subprocess.run(
            tokens,
            cwd=base,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TEST_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            False,
            f"Команда не успела за {TEST_TIMEOUT} секунд.",
        )
    except OSError as error:
        return ToolResult(False, f"Не удалось выполнить: {error}")

    output = (result.stdout + result.stderr).strip()
    tail = output[-4000:] if output else "вывод пуст"

    add_action(
        "Агент: команда " + " ".join(tokens[:3])
    )

    return ToolResult(
        result.returncode == 0,
        f"код {result.returncode}\n{tail}",
    )

