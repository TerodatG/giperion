# Giperion/tools/audit.py                                             v001
# Аудит проекта: размеры, связи модулей, циклы и «сироты».
#
# Пример:
#   python -m tools.audit
#   python -m tools.audit --limit 15

import argparse
import ast
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKIP_TOP = {
    ".git", ".venv", "venv", "env", "node_modules", "logs", "archive",
    "models", ".agent_plugin_tmp", "dist", "build", "data", ".orchestra",
}

SKIP_ANY = {"__pycache__", ".pytest_cache", ".mypy_cache"}

FILE_LIMIT = 600
FUNCTION_LIMIT = 80

# Точки входа: их никто не импортирует, это нормально.
ENTRY_POINTS = {
    "main", "gui", "config",
    "terminal.api.cli", "tools.audit",
}


def project_files(root: Path) -> list[Path]:
    """Все Python-файлы проекта, кроме служебных папок."""

    files = []

    for path in root.rglob("*.py"):
        parts = path.relative_to(root).parts

        if not parts:
            continue

        if parts[0] in SKIP_TOP or set(parts) & SKIP_ANY:
            continue

        files.append(path)

    return sorted(files)


def module_name(root: Path, path: Path) -> str:
    """Имя модуля для импортов: terminal.core.agent.loop."""

    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)

    if parts and parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts)


def imports_of(path: Path, root: Path) -> set[str]:
    """Импорты, ведущие внутрь проекта (с учётом относительных)."""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    module = module_name(root, path)
    is_package = path.name == "__init__.py"
    package = module if is_package else module.rpartition(".")[0]
    found = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""

            if node.level:
                parts = package.split(".") if package else []
                drop = node.level - 1

                if drop:
                    parts = parts[:-drop] if drop <= len(parts) else []

                base = ".".join([*parts, base] if base else parts)

            if base:
                found.add(base)

                for alias in node.names:
                    found.add(f"{base}.{alias.name}")

    return found


def big_functions(path: Path) -> list[tuple[str, int]]:
    """Функции длиннее лимита."""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    found = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        end = getattr(node, "end_lineno", node.lineno)
        length = end - node.lineno + 1

        if length > FUNCTION_LIMIT:
            found.append((node.name, length))

    return found


def build_graph(root: Path, files: list[Path]) -> dict[str, set[str]]:
    """Граф «модуль → модули проекта, которые он импортирует»."""

    known = {module_name(root, path) for path in files}
    graph: dict[str, set[str]] = {}

    for path in files:
        name = module_name(root, path)
        edges = set()

        for imported in imports_of(path, root):
            parts = imported.split(".")

            for cut in range(len(parts), 0, -1):
                candidate = ".".join(parts[:cut])

                if candidate in known and candidate != name:
                    edges.add(candidate)
                    break

        graph[name] = edges

    return graph


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Ищет циклы в графе импортов (DFS с серым множеством)."""

    cycles: list[list[str]] = []
    seen: set[str] = set()

    def walk(node: str, stack: list[str], active: set[str]) -> None:
        if node in active:
            index = stack.index(node)
            cycles.append(stack[index:] + [node])

            return

        if node in seen:
            return

        active.add(node)
        stack.append(node)

        for neighbour in sorted(graph.get(node, ())):
            walk(neighbour, stack, active)

        stack.pop()
        active.discard(node)
        seen.add(node)

    for node in sorted(graph):
        walk(node, [], set())

    return cycles


def orphans(graph: dict[str, set[str]], root: Path) -> list[str]:
    """Модули, которые никто не импортирует."""

    imported = {edge for edges in graph.values() for edge in edges}
    used = set(imported)

    # Пакет считается используемым, если импортируют его подмодуль.
    for name in graph:
        prefix = name + "."

        if any(other.startswith(prefix) for other in imported):
            used.add(name)

    return sorted(
        name
        for name in graph
        if name not in used
        and name not in ENTRY_POINTS
        and not name.startswith("tests")
        and not name.startswith("tools")
    )


def report(root: Path, limit: int) -> int:
    """Печатает отчёт и возвращает код выхода."""

    files = project_files(root)
    problems = 0

    sizes = sorted(
        ((len(path.read_text(encoding="utf-8").splitlines()), path)
         for path in files),
        reverse=True,
    )

    print(f"файлов: {len(files)}")

    print("\n== крупные файлы (лимит %d)" % FILE_LIMIT)

    for lines, path in sizes[:limit]:
        if lines <= FILE_LIMIT:
            break

        print(f"  {lines:5d}  {path.relative_to(root)}")
        problems += 1

    print("\n== длинные функции (лимит %d)" % FUNCTION_LIMIT)

    for path in files:
        for name, length in big_functions(path):
            print(f"  {length:5d}  {path.relative_to(root)}::{name}")
            problems += 1

    graph = build_graph(root, files)
    cycles = find_cycles(graph)

    print("\n== циклы импортов")

    if not cycles:
        print("  нет")

    for cycle in cycles[:limit]:
        print("  " + " -> ".join(cycle))
        problems += 1

    loose = orphans(graph, root)

    print("\n== модули без импортов")

    for name in loose[:limit]:
        print(f"  {name}")

    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Аудит проекта.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--check",
        action="store_true",
        help="строгий режим: циклы и крупные файлы кода",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if args.check:
        return check(root)

    return report(root, args.limit)


def check(root: Path) -> int:
    """Строгая проверка для CI: циклы и крупные файлы кода."""

    files = project_files(root)
    problems = []

    for path in files:
        relative = path.relative_to(root)

        if relative.parts[0] == "tests":
            continue

        lines = len(path.read_text(encoding="utf-8").splitlines())

        if lines > FILE_LIMIT:
            problems.append(f"{relative}: {lines} строк")

    for cycle in find_cycles(build_graph(root, files)):
        problems.append("цикл: " + " -> ".join(cycle))

    if problems:
        for problem in problems:
            print("ОШИБКА ·", problem)

        return 1

    print(f"OK · файлов {len(files)}, циклов нет")

    return 0


if __name__ == "__main__":
    sys.exit(main())
