# Giperion/tests/test_plugin_install.py                                v001
# Установщик плагинов: валидация, копирование и хеши.

import json

import pytest

from tools import plugin_install


def _plugin(
    tmp_path,
    name="word_count",
    module="plugin.py",
    folder_name="source",
):
    folder = tmp_path / folder_name
    folder.mkdir(exist_ok=True)
    (folder / "plugin.py").write_text(
        "def handler(args, root):\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    (folder / f"{name}.json").write_text(
        json.dumps(
            {
                "name": name,
                "description": "Считает слова",
                "risk": "read",
                "module": module,
                "args": {"text": "текст"},
                "permissions": ["fs:read"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return folder


def test_validate_and_install(tmp_path) -> None:
    """Плагин проверяется и копируется с хешами."""

    folder = _plugin(tmp_path)
    document, _manifest, modules = plugin_install.validate(folder)

    assert document["name"] == "word_count"
    assert len(modules) == 1

    target = tmp_path / "tools"
    result = plugin_install.install(
        folder,
        target=target,
        allow_unsigned=True,
    )

    installed = target / "word_count"
    manifest = json.loads(
        (installed / "word_count.json").read_text(encoding="utf-8")
    )

    assert result["files"] == 1
    assert (installed / "plugin.py").is_file()
    assert manifest["sha256"]["plugin.py"]
    assert manifest["installed_at"]


def test_conflict_requires_force(tmp_path) -> None:
    """Повторная установка без --force запрещена."""

    folder = _plugin(tmp_path)
    target = tmp_path / "tools"
    plugin_install.install(
        folder,
        target=target,
        allow_unsigned=True,
    )

    with pytest.raises(ValueError):
        plugin_install.install(
            folder,
            target=target,
            allow_unsigned=True,
        )

    assert plugin_install.install(
        folder,
        target=target,
        force=True,
        allow_unsigned=True,
    )["name"] == "word_count"


def test_unsigned_is_rejected_by_default(tmp_path) -> None:
    """Без подписи установка блокируется, пока не разрешена явно."""

    folder = _plugin(tmp_path)

    with pytest.raises(ValueError, match="Подпись"):
        plugin_install.install(
            folder,
            target=tmp_path / "tools",
        )

    assert plugin_install.install(
        folder,
        target=tmp_path / "tools",
        allow_unsigned=True,
    )["name"] == "word_count"


def test_invalid_manifest(tmp_path) -> None:
    """Имя, risk и модуль проверяются."""

    folder = _plugin(
        tmp_path,
        name="Bad Name",
        module="missing.py",
        folder_name="bad",
    )

    with pytest.raises(ValueError):
        plugin_install.validate(folder)

    folder = _plugin(tmp_path, name="upper", folder_name="risk")
    manifest = folder / "upper.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["risk"] = "danger"
    manifest.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError):
        plugin_install.validate(folder)
