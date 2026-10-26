# Giperion/tools/check_structure.py                                  v001
# Отчёт о перегруженных файлах и функциях проекта.
# Последнее изменение: первый отчёт — файлы, функции и сложность.

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE_ROOTS = ("model/giperion_model", "terminal", "shared", "tools")
SOURCE_FILES = ("gui.py", "main.py", "config.py")
SKIP_PARTS = {"__pycache__", ".pytest_cache"}

FILE_LIMIT = 600
FUNCTION_LIMIT = 150
COMPLEXITY_LIMIT = 20


def source_files() -> list[Path]:
    """Файлы приложения без тестов и служебных папок."""

    files = []

    for name in SOURCE_FILES:
        path = ROOT / name

        if path.is_file():
            files.append(path)

    for root in SOURCE_ROOTS:
        for path in (ROOT / root).rglob("*.py"):
            if any(part in SKIP_PARTS for part in path.parts):
                continue

            if "tests" in path.relative_to(ROOT).parts:
                continue

            files.append(path)

    return sorted(set(files))


def complexity(node: ast.AST) -> int:
    """Приблизительная цикломатическая сложность функции."""

    score = 1

    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.ExceptHandler,
                ast.Assert,
                ast.IfExp,
                ast.comprehension,
            ),
        ):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += len(child.values) - 1
        elif isinstance(child, ast.Match):
            score += len(child.cases)

    return score


def inspect(path: Path) -> tuple[list[str], list[str], list[str]]:
    """Возвращает замечания по файлу, функциям и сложности."""

    relative = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding="utf-8")
    lines = len(text.splitlines())
    file_notes = []

    if lines > FILE_LIMIT:
        file_notes.append(f"{relative}: {lines} строк (лимит {FILE_LIMIT})")

    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        file_notes.append(f"{relative}: синтаксис — {error}")
        return file_notes, [], []

    function_notes = []
    complexity_notes = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        end = getattr(node, "end_lineno", node.lineno)
        length = end - node.lineno + 1

        if length > FUNCTION_LIMIT:
            function_notes.append(
                f"{relative}:{node.lineno} {node.name} — "
                f"{length} строк"
            )

        score = complexity(node)

        if score > COMPLEXITY_LIMIT:
            complexity_notes.append(
                f"{relative}:{node.lineno} {node.name} — C={score}"
            )

    return file_notes, function_notes, complexity_notes


def main() -> int:
    """Печатает отчёт; --strict возвращает код 1 при нарушениях."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict",
        action="store_true",
        help="вернуть код 1, если есть перегруженные места",
    )
    args = parser.parse_args()

    files: list[str] = []
    functions: list[str] = []
    complex_functions: list[str] = []

    for path in source_files():
        file_notes, function_notes, complexity_notes = inspect(path)
        files.extend(file_notes)
        functions.extend(function_notes)
        complex_functions.extend(complexity_notes)

    print(f"Файлы > {FILE_LIMIT} строк: {len(files)}")
    print(f"Функции > {FUNCTION_LIMIT} строк: {len(functions)}")
    print(f"Функции C > {COMPLEXITY_LIMIT}: {len(complex_functions)}")

    for title, notes in (
        ("ФАЙЛЫ", files),
        ("ФУНКЦИИ", functions),
        ("СЛОЖНОСТЬ", complex_functions),
    ):
        if not notes:
            continue

        print(f"\n{title}:")

        for note in notes:
            print(f"  {note}")

    if args.strict and (files or functions or complex_functions):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
