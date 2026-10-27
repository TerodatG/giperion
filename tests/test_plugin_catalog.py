# Giperion/tests/test_plugin_catalog.py                                 v001
# Каталог плагинов: список, поиск и установка по имени.

import json

import pytest

from tools import plugin_catalog


def _catalog(tmp_path):
    source = tmp_path / "catalog" / "word"
    source.mkdir(parents=True)
    (source / "plugin.py").write_text(
        "def handler(args, root):\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    (source / "word.json").write_text(
        json.dumps(
            {
                "name": "word",
                "description": "Считает слова",
                "risk": "read",
                "module": "plugin.py",
                "args": {"text": "текст"},
                "permissions": ["fs:read"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "plugins": [
                    {
                        "name": "word",
                        "path": "catalog/word",
                        "description": "Считает слова",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return catalog


def test_load_and_find(tmp_path) -> None:
    """Каталог читается, имя ищется без регистра."""

    catalog = _catalog(tmp_path)

    assert plugin_catalog.load(catalog)[0]["name"] == "word"
    assert plugin_catalog.find("WORD", catalog)["path"] == "catalog/word"
    assert plugin_catalog.find("missing", catalog) is None


def test_install_by_name(tmp_path) -> None:
    """Относительный путь каталога разрешается от JSON-файла."""

    catalog = _catalog(tmp_path)
    target = tmp_path / "tools"

    result = plugin_catalog.install(
        "word",
        catalog,
        target=target,
        allow_unsigned=True,
    )

    assert result["name"] == "word"
    assert (target / "word" / "plugin.py").is_file()


def test_unknown_name_is_rejected(tmp_path) -> None:
    """Неизвестное имя не устанавливается."""

    catalog = _catalog(tmp_path)

    with pytest.raises(ValueError, match="не найден"):
        plugin_catalog.install("missing", catalog)
