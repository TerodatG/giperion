# Giperion/tools/build_portable.py                                    v001
# Собирает переносимую папку проекта в zip без данных и моделей.
# Последнее изменение: первый вариант — include/exclude и проверка.

import argparse
import sys
import zipfile
from pathlib import Path

from config import BASE_DIR

INCLUDE_DIRS = (
    "terminal",
    "giperion",
    "shared",
    "tools",
    "docs",
    "knowledge",
    "skins",
)
INCLUDE_FILES = (
    "config.py",
    "gui.py",
    "main.py",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "README.md",
    "DEVLOG.md",
)
EXCLUDE_DIRS = {
    ".git",
    ".agent_worktrees",
    "data",
    "models",
    "updates",
    "__pycache__",
    ".venv",
    "venv",
    "archive",
    "logs",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
NOTE = """Giperion — переносимая копия
=============================

1. Установите зависимости:
   python -m pip install -r requirements.txt
2. Запустите:
   python main.py

Данные, история, кеши и модели в архив не входят: они создаются заново
в папке data/ при первом запуске.
"""


def iter_files(
    root: Path,
    include_tests: bool = False,
) -> list[Path]:
    """Файлы, которые попадут в архив."""

    base = Path(root)
    files: list[Path] = []

    for name in INCLUDE_FILES:
        path = base / name

        if path.is_file():
            files.append(path)

    dirs = list(INCLUDE_DIRS)

    if include_tests:
        dirs.append("tests")

    for name in dirs:
        folder = base / name

        if not folder.is_dir():
            continue

        for path in folder.rglob("*"):
            if not path.is_file():
                continue

            if any(part in EXCLUDE_DIRS for part in path.parts):
                continue

            if path.suffix.lower() in EXCLUDE_SUFFIXES:
                continue

            files.append(path)

    return files


def build(
    output: Path,
    root: Path = BASE_DIR,
    include_tests: bool = False,
) -> Path:
    """Пишет zip и возвращает путь."""

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    base = Path(root)
    files = iter_files(base, include_tests)

    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in files:
            archive.write(path, path.relative_to(base).as_posix())

        archive.writestr("PORTABLE.txt", NOTE)

    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Собрать переносимую версию Giperion в zip.",
    )
    parser.add_argument(
        "--output",
        default="dist/giperion-portable.zip",
    )
    parser.add_argument("--with-tests", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="только показать список файлов",
    )
    args = parser.parse_args()

    if args.check:
        for path in iter_files(BASE_DIR, args.with_tests):
            print(path.relative_to(BASE_DIR).as_posix())

        return 0

    target = build(
        Path(args.output),
        BASE_DIR,
        args.with_tests,
    )
    size = target.stat().st_size / 1024 / 1024

    print(f"Собрано: {target} ({size:.1f} МБ)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
