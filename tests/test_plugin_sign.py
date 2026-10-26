# Giperion/tests/test_plugin_sign.py                                   v001
# Подпись плагина: ключ, проверка и установка.

import json

import pytest

from tools import plugin_install, plugin_sign


def _plugin(tmp_path):
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "plugin.py").write_text(
        "def handler(args, root):\n    return {'ok': True}\n",
        encoding="utf-8",
    )
    (folder / "word_count.json").write_text(
        json.dumps(
            {
                "name": "word_count",
                "description": "Считает слова",
                "risk": "read",
                "module": "plugin.py",
                "args": {"text": "текст"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return folder


@pytest.fixture(autouse=True)
def _key(tmp_path, monkeypatch):
    key = tmp_path / "key"
    monkeypatch.setattr(plugin_sign, "KEY_FILE", key)

    return key


def test_sign_and_verify(tmp_path) -> None:
    """Подпись проверяется, подмена файла ловится."""

    folder = _plugin(tmp_path)

    signature = plugin_sign.sign(folder)

    assert signature.is_file()

    ok, message = plugin_sign.verify(folder)

    assert ok
    assert "верна" in message

    (folder / "plugin.py").write_text("print('evil')", encoding="utf-8")
    ok, message = plugin_sign.verify(folder)

    assert not ok
    assert "изменились" in message


def test_install_requires_signature(tmp_path) -> None:
    """С флагом подписи неподписанный плагин не ставится."""

    folder = _plugin(tmp_path)
    target = tmp_path / "tools"

    with pytest.raises(ValueError):
        plugin_install.install(
            folder,
            target=target,
            require_signature=True,
        )

    plugin_sign.sign(folder)
    result = plugin_install.install(
        folder,
        target=target,
        require_signature=True,
    )

    assert result["name"] == "word_count"


def test_tampered_plugin_is_rejected(tmp_path) -> None:
    """Подписанный, но изменённый плагин не устанавливается."""

    folder = _plugin(tmp_path)
    plugin_sign.sign(folder)
    (folder / "plugin.py").write_text("print('evil')", encoding="utf-8")

    with pytest.raises(ValueError):
        plugin_install.install(
            folder,
            target=tmp_path / "tools",
            require_signature=True,
        )
