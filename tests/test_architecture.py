# Giperion/tests/test_architecture.py                               v002
# Граница между отдельным проектом модели (giperion_model) и агентом.
# Последнее изменение: модель вынесена в model/, граница расширена.

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Модель: самостоятельный проект model/ с пакетом giperion_model.
MODEL_ROOTS = ("model/giperion_model",)

MODEL_FILES: tuple[str, ...] = ()

# Агент и общий слой приложения модели недоступны: у неё свой config
# и _shared. Иначе граница снова размоется.
FORBIDDEN_PREFIXES = ("terminal", "shared", "config")


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

    assert files, "Не найдено ни одного файла модели"

    violations = []

    for path in files:
        for module, names in imported_modules(path):
            target = forbidden_target(module, names)

            if target:
                violations.append(
                    f"{path.relative_to(ROOT).as_posix()}: {target}"
                )

    assert not violations, (
        "Модель импортирует агента (границу нарушать нельзя):\n"
        + "\n".join(violations)
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
