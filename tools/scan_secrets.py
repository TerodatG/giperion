# Giperion/tools/scan_secrets.py                                      v001
# Поиск секретов в отслеживаемых файлах перед коммитом.
# Последнее изменение: первый вариант — redact по файлам, --all и --json.

import argparse
import json
import sys
from pathlib import Path

from config import BASE_DIR
from terminal.core.agent.redact import redact

DEFAULT_DIRS = (
    "terminal",
    "giperion",
    "shared",
    "tools",
    "config.py",
    "main.py",
    "gui.py",
)
SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".txt",
    ".cfg",
    ".ini",
}
MAX_BYTES = 400_000
SKIP_PARTS = {
    ".git",
    "__pycache__",
    "data",
    "models",
    ".venv",
    "node_modules",
    "archive",
}
SKIP_FILES = {
    "terminal/core/agent/redact.py",
}


def _files(paths: list[str], include_tests: bool) -> list[Path]:
    """Текстовые файлы выбранных каталогов."""

    found: list[Path] = []

    for name in paths:
        target = (BASE_DIR / name).resolve()

        if target.is_file():
            try:
                relative = target.relative_to(BASE_DIR).as_posix()
            except ValueError:
                relative = ""

            if relative not in SKIP_FILES:
                found.append(target)

            continue

        if not target.is_dir():
            continue

        for path in target.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUFFIXES:
                continue

            if any(part in SKIP_PARTS for part in path.parts):
                continue

            relative = path.relative_to(BASE_DIR).as_posix()

            if relative in SKIP_FILES:
                continue

            if not include_tests and relative.startswith("tests/"):
                continue

            try:
                if path.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue

            found.append(path)

    return found


def scan(paths: list[str], include_tests: bool = False) -> list[dict]:
    """Файлы, где redact нашёл секреты."""

    problems = []

    for path in _files(paths, include_tests):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        result = redact(text)

        if not result.hidden:
            continue

        try:
            relative = path.relative_to(BASE_DIR).as_posix()
        except ValueError:
            relative = str(path)

        problems.append(
            {
                "path": relative,
                "hidden": result.hidden,
            }
        )

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ищет секреты в файлах проекта через redact.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=list(DEFAULT_DIRS),
        help="файлы или каталоги (по умолчанию исходники)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="включая tests/",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    problems = scan(args.paths or list(DEFAULT_DIRS), args.all)

    if args.json:
        print(json.dumps(problems, ensure_ascii=False, indent=2))
    elif problems:
        for item in problems:
            print(
                f"{item['path']}: похоже на секреты "
                f"({item['hidden']})"
            )
    else:
        print("Секретов не найдено.")

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
