# Giperion/tests/test_sources.py                                     v001
# Исходники проекта: UTF-8 без BOM и без обрезанных файлов.
# Последнее изменение: первый тест — BOM ломал ast.parse в инструментах.

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {
    ".git",
    ".agent_worktrees",
    "archive",
    "__pycache__",
    ".pytest_cache",
    "data",
    "logs",
    "models",
    "updates",
}


def source_files() -> list[Path]:
    """Все Python-файлы проекта, которые мы поддерживаем руками."""

    files = []

    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue

        files.append(path)

    return sorted(files)


def test_python_sources_are_utf8_without_bom() -> None:
    """BOM ломает ast.parse у инструментов и внешних линтеров."""

    problems = []

    for path in source_files():
        data = path.read_bytes()

        if data.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{path.relative_to(ROOT).as_posix()}: BOM")

            continue

        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            problems.append(
                f"{path.relative_to(ROOT).as_posix()}: {error}"
            )

    assert not problems, "Проблемы кодировки:\n" + "\n".join(problems)
