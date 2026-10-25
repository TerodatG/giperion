# Giperion/tests/test_import_graph.py                                v001
# Граф импортов: не даём появиться новым циклам между модулями.
# Последнее изменение: три известных цикла зафиксированы до рефакторинга.

import ast
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE_ROOTS = ("giperion", "terminal", "shared", "tools")

# Циклы, которые уже есть и разбираются отдельным этапом.
# После развязки агента список должен стать пустым.
KNOWN_CYCLES = {
    frozenset(
        {
            "giperion.neural_engine",
            "giperion.neural_loader",
        }
    ),
    frozenset(
        {
            "terminal.core.agent.context",
            "terminal.core.agent.mcp",
            "terminal.core.agent.plugin_runner",
            "terminal.core.agent.providers",
            "terminal.core.agent.registry",
            "terminal.core.agent.settings",
        }
    ),
    frozenset(
        {
            "terminal.ui.agent_dialog",
            "terminal.ui.agent_tasks_dialog",
        }
    ),
}


def module_name(path: Path) -> str:
    """Имя модуля из пути: terminal/core/agent/loop.py → terminal.core..."""

    relative = path.relative_to(ROOT).as_posix()

    if relative.endswith("/__init__.py"):
        relative = relative[: -len("/__init__.py")]
    elif relative.endswith(".py"):
        relative = relative[:-3]

    return relative.replace("/", ".")


def source_files() -> list[Path]:
    """Модули приложения, участвующие в графе импортов."""

    files = []

    for root in SOURCE_ROOTS:
        for path in (ROOT / root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue

            files.append(path)

    return sorted(files)


def build_graph() -> dict[str, set[str]]:
    """Строит граф внутренних импортов, включая импорты внутри функций."""

    files = source_files()
    modules = {module_name(path) for path in files}
    graph: dict[str, set[str]] = defaultdict(set)

    for path in files:
        current = module_name(path)

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as error:
            raise AssertionError(f"{path}: {error}") from error

        for node in ast.walk(tree):
            targets: list[str] = []

            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
            ):
                targets = [node.module]

                for alias in node.names:
                    full = f"{node.module}.{alias.name}"

                    if full in modules:
                        targets.append(full)

            for target in targets:
                if target in modules and target != current:
                    graph[current].add(target)

    return graph


def strongly_connected(graph: dict[str, set[str]]) -> list[frozenset[str]]:
    """Ищет компоненты сильной связности алгоритмом Тарьяна."""

    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    components: list[frozenset[str]] = []
    counter = [0]

    def visit(node: str) -> None:
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)

        for child in graph.get(node, ()):
            if child not in index:
                visit(child)
                low[node] = min(low[node], low[child])
            elif child in on_stack:
                low[node] = min(low[node], index[child])

        if low[node] != index[node]:
            return

        component = set()

        while True:
            item = stack.pop()
            on_stack.discard(item)
            component.add(item)

            if item == node:
                break

        if len(component) > 1:
            components.append(frozenset(component))

    for node in graph:
        if node not in index:
            visit(node)

    return components


def test_import_graph_has_no_new_cycles() -> None:
    """Новый цикл импорта должен падать здесь, а не через полгода."""

    graph = build_graph()
    found = set(strongly_connected(graph))
    unexpected = found - KNOWN_CYCLES

    assert not unexpected, (
        "Появились новые циклы импорта:\n"
        + "\n".join(
            " ↔ ".join(sorted(component))
            for component in sorted(unexpected, key=sorted)
        )
    )


def test_known_cycles_are_still_present() -> None:
    """Когда цикл развязан, его нужно убрать из списка известных."""

    graph = build_graph()
    found = set(strongly_connected(graph))
    stale = KNOWN_CYCLES - found

    assert not stale, (
        "Эти циклы уже исчезли — уберите их из KNOWN_CYCLES:\n"
        + "\n".join(
            " ↔ ".join(sorted(component))
            for component in sorted(stale, key=sorted)
        )
    )
