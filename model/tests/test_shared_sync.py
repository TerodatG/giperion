# GiperionModel/tests/test_shared_sync.py                              v001
# Синхронизация копий общего слоя с корневым shared/.

from pathlib import Path

MODEL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODEL_ROOT.parent
SHARED_ROOT = MODEL_ROOT / "giperion_model" / "_shared"

# Копии модели и их оригиналы в корневом shared/.
PAIRS = {
    "action_log.py": "shared/action_log.py",
    "json_store.py": "shared/storage/json_store.py",
    "text_tools.py": "shared/text_tools.py",
}

# Модель не может импортировать корневые пакеты, поэтому импорты
# в копиях заменены на giperion_model.*. Перед сравнением приводим
# их к одному виду.
IMPORT_REWRITES = (
    (
        "from giperion_model.config import",
        "from config import",
    ),
    (
        "from giperion_model._shared.json_store import",
        "from shared.storage.json_store import",
    ),
)


def normalized(path: Path) -> str:
    """Текст без заголовка, с общими именами и порядком импортов."""

    lines = path.read_text(encoding="utf-8").splitlines()[1:]
    text = "\n".join(lines).strip()

    for source, target in IMPORT_REWRITES:
        text = text.replace(source, target)

    return "\n".join(_sorted_imports(text.splitlines()))


def _sorted_imports(lines: list[str]) -> list[str]:
    """Сортирует соседние группы импортов, не трогая остальной код."""

    result: list[str] = []
    block: list[str] = []

    def flush() -> None:
        result.extend(sorted(block))
        block.clear()

    for line in lines:
        if line.startswith(("import ", "from ")):
            block.append(line)
            continue

        flush()
        result.append(line)

    flush()

    return result


def test_shared_copies_are_listed() -> None:
    """Каждая копия общего слоя должна иметь оригинал в списке."""

    copies = {
        path.name
        for path in SHARED_ROOT.glob("*.py")
        if path.name != "__init__.py"
    }

    assert copies == set(PAIRS), (
        "Список копий _shared разошёлся с файлами: "
        f"{sorted(copies)} != {sorted(PAIRS)}"
    )


def test_shared_copies_match_root() -> None:
    """Копии модели не должны незаметно расходиться с shared/."""

    drifted = []

    for copy_name, original_name in PAIRS.items():
        copy_path = SHARED_ROOT / copy_name
        original_path = REPO_ROOT / original_name

        if not original_path.is_file():
            drifted.append(f"{original_name}: оригинала нет")
            continue

        if normalized(copy_path) != normalized(original_path):
            drifted.append(
                f"{copy_name} != {original_name}"
            )

    assert not drifted, (
        "Общий слой модели разошёлся с корневым shared/:\n"
        + "\n".join(drifted)
    )
