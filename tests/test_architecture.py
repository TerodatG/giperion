# Giperion/tests/test_architecture.py                               v003
# Граница между отдельным проектом модели (kraper_model) и агентом.
# Последнее изменение: запрещены UI-импорты, добавлена runtime-проверка.

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Kraper — отдельный проект в соседней папке.
MODEL_ROOT = Path(
    os.environ.get(
        "KRAPER_MODEL_PATH",
        str(ROOT.parent / "Kraper" / "kraper_model"),
    )
)

MODEL_ROOTS = (MODEL_ROOT,)

MODEL_FILES: tuple[str, ...] = ()

# Агент, UI и общий слой приложения модели недоступны: у неё свой config
# и _shared. Иначе граница снова размоется.
FORBIDDEN_PREFIXES = (
    "terminal",
    "shared",
    "config",
    "gui",
    "main",
    "PySide6",
)


def model_files() -> list[Path]:
    """Собирает файлы модели, которые уже существуют в репозитории."""

    files: list[Path] = []

    for root in MODEL_ROOTS:
        path = ROOT / root

        if path.is_dir():
            files.extend(
                file
                for file in path.rglob("*.py")
                if "__pycache__" not in file.parts
            )

    for name in MODEL_FILES:
        path = ROOT / name

        if path.is_file():
            files.append(path)

    return files


def imported_modules(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    """Возвращает импорты файла: модуль и импортированные имена."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, ()))
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
        ):
            names = tuple(alias.name for alias in node.names)
            found.append((node.module, names))

    return found


def forbidden_target(module: str, names: tuple[str, ...]) -> str | None:
    """Возвращает описание нарушения или None."""

    for prefix in FORBIDDEN_PREFIXES:
        if module == prefix or module.startswith(prefix + "."):
            return module

    return None


def test_model_does_not_import_agent() -> None:
    """Модель не должна знать про интерфейс, память, навыки и агента."""

    files = model_files()

    if not files:
        pytest.skip("Kraper не найден рядом с терминалом")

    violations = []

    for path in files:
        for module, names in imported_modules(path):
            target = forbidden_target(module, names)

            if target:
                violations.append(
                    f"{path.as_posix()}: {target}"
                )

    assert not violations, (
        "Модель импортирует агента (границу нарушать нельзя):\n"
        + "\n".join(violations)
    )


def test_model_api_import_stays_independent() -> None:
    """Импорт точки входа модели не тянет терминал, UI и корневой shared."""

    if not model_files():
        pytest.skip("Kraper не найден рядом с терминалом")

    probe = (
        "import json, sys\n"
        "import kraper_model.api\n"
        "roots = {'terminal', 'shared', 'config', 'main', 'gui', "
        "'PySide6'}\n"
        "found = sorted(\n"
        "    name\n"
        "    for name in sys.modules\n"
        "    if name in roots\n"
        "    or name.startswith(('terminal.', 'shared.', 'PySide6.'))\n"
        ")\n"
        "print(json.dumps(found))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr

    found = result.stdout.strip().splitlines()[-1]

    assert found == "[]", (
        "Импорт kraper_model.api подтянул чужие модули: " + found
    )


def test_production_code_uses_catalog_not_registry_facade() -> None:
    """Рабочий код ходит в конкретные модули, а не в фасад."""

    files = [
        path
        for path in (ROOT / "terminal").rglob("*.py")
        if "__pycache__" not in path.parts
        and path.name != "model_registry.py"
    ]
    files.append(ROOT / "gui.py")
    violations = []

    for path in files:
        for module, _names in imported_modules(path):
            if (
                module == "terminal.core.model_registry"
                or module.startswith("terminal.core.model_registry.")
            ):
                violations.append(
                    f"{path.relative_to(ROOT).as_posix()}: {module}"
                )

    assert not violations, (
        "Фасад model_registry снова попал в рабочий код:\n"
        + "\n".join(violations)
    )
