# Giperion/app/core/personality_catalog.py                        v002
# Каталог личностных матриц: будущие модели поведения Гипериона.
# Последнее изменение: чтение и запись через общий json_store.

from pathlib import Path

from shared.storage.json_store import read_json, write_json
from config import DATA_DIR

PERSONALITIES_FILE = DATA_DIR / "personality_matrices.json"
SETTINGS_FILE = DATA_DIR / "personality_settings.json"


def _read_document(path: Path) -> dict:
    """Читает JSON-документ и возвращает пустой словарь при ошибке."""

    document = read_json(path, {})

    return document if isinstance(document, dict) else {}


def _write_document(path: Path, document: dict) -> None:
    """Сохраняет JSON-документ с русскими подписями."""

    write_json(path, document)


def _clean_traits(value: object) -> dict[str, int]:
    """Проверяет оценки характера по шкале 0–5."""

    if not isinstance(value, dict):
        return {}

    traits = {}

    for name, score in value.items():
        if not isinstance(name, str):
            continue

        try:
            traits[name] = max(0, min(5, int(score)))
        except (TypeError, ValueError):
            continue

    return traits


def _parse_matrix(record: object) -> dict | None:
    """Превращает запись каталога в проверенную личностную матрицу."""

    if not isinstance(record, dict):
        return None

    matrix_id = record.get("id")
    name = record.get("name")

    if not isinstance(matrix_id, str) or not isinstance(name, str):
        return None

    symbol = record.get("symbol")
    matrix = {
        "id": matrix_id,
        "name": name,
        "role": str(record.get("role", "")),
        "symbol": symbol if isinstance(symbol, str) else "◈",
        "motto": str(record.get("motto", "")),
        "description": str(record.get("description", "")),
        "traits": _clean_traits(record.get("traits")),
        "speech": str(record.get("speech", "")),
        "strengths": str(record.get("strengths", "")),
        "risks": str(record.get("risks", "")),
        "status": str(
            record.get("status", "Будущая модель поведения")
        ),
    }

    return matrix


def load_personality_matrices(
    path: Path | None = None,
) -> list[dict]:
    """Читает каталог личностных матриц."""

    document = _read_document(path or PERSONALITIES_FILE)
    matrices = []

    for record in document.get("matrices", []):
        matrix = _parse_matrix(record)

        if matrix is not None:
            matrices.append(matrix)

    return matrices


def get_personality(
    matrix_id: str,
    matrices: list[dict] | None = None,
) -> dict | None:
    """Возвращает матрицу по идентификатору или None."""

    for matrix in matrices or load_personality_matrices():
        if matrix["id"] == matrix_id:
            return matrix

    return None


def get_selected_personality_id(
    path: Path | None = None,
) -> str:
    """Возвращает сохранённый выбор или первую доступную матрицу."""

    matrices = load_personality_matrices()
    known_ids = [matrix["id"] for matrix in matrices]
    document = _read_document(path or SETTINGS_FILE)
    selected = document.get("selected")

    if isinstance(selected, str) and selected in known_ids:
        return selected

    return known_ids[0] if known_ids else ""


def set_selected_personality_id(
    matrix_id: str,
    path: Path | None = None,
) -> bool:
    """Сохраняет выбранную матрицу, если она есть в каталоге."""

    if get_personality(matrix_id) is None:
        return False

    file_path = path or SETTINGS_FILE
    document = _read_document(file_path)
    document["selected"] = matrix_id

    try:
        _write_document(file_path, document)
    except OSError:
        return False

    return True
