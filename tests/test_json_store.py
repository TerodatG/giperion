# Giperion/tests/test_json_store.py                                v001
# Проверки общего слоя хранения: чтение, атомарная запись, кириллица.

from app.storage.json_store import read_json, read_json_object, write_json


def test_missing_file_returns_default(tmp_path) -> None:
    """Отсутствующий файл не считается ошибкой."""

    path = tmp_path / "missing.json"

    assert read_json(path, {"fallback": True}) == {"fallback": True}


def test_corrupted_file_returns_default(tmp_path) -> None:
    """Испорченный JSON не роняет приложение."""

    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    assert read_json(path, []) == []


def test_object_reader_ignores_other_types(tmp_path) -> None:
    """Функция для объектов не принимает список или строку."""

    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    assert read_json_object(path) == {}


def test_write_read_roundtrip(tmp_path) -> None:
    """Запись сохраняет структуру и кириллицу."""

    path = tmp_path / "nested" / "document.json"
    document = {
        "name": "Гиперион",
        "levels": [1, 2, 3],
    }

    write_json(path, document)

    assert read_json(path, None) == document
    assert "Гиперион" in path.read_text(encoding="utf-8")


def test_write_replaces_old_content(tmp_path) -> None:
    """Новая запись полностью заменяет старый документ."""

    path = tmp_path / "data.json"
    write_json(path, {"old": True})
    write_json(path, {"new": True})

    assert read_json(path, None) == {"new": True}


def test_write_does_not_leave_temporary_files(tmp_path) -> None:
    """После записи в каталоге не остаётся временных файлов."""

    path = tmp_path / "document.json"

    write_json(path, {"ok": True})

    names = {item.name for item in tmp_path.iterdir()}

    assert names == {path.name}


def test_failed_write_keeps_previous_file(tmp_path) -> None:
    """Неудачная сериализация не портит старый документ."""

    path = tmp_path / "document.json"

    write_json(path, {"version": 1})

    try:
        write_json(path, {"bad": object()})
    except TypeError:
        pass
    else:
        raise AssertionError("запись несериализуемых данных должна падать")

    assert read_json(path, None) == {"version": 1}

    names = {item.name for item in tmp_path.iterdir()}

    assert names == {path.name}


def test_trailing_newline_is_optional(tmp_path) -> None:
    """Флаг добавляет перевод строки, как у intents.json."""

    path = tmp_path / "intents.json"

    write_json(path, {"intents": []}, trailing_newline=True)

    assert path.read_text(encoding="utf-8").endswith("\n")
