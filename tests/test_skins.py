# Giperion/tests/test_skins.py                                       v002
# Каталог скинов интерфейса и сохранение выбора.
# Последнее изменение: скины и текстуры в папках skins/.

import pytest

from terminal.core import skins, window_settings


@pytest.fixture()
def settings_file(tmp_path, monkeypatch):
    """Изолирует файл настроек окна."""

    path = tmp_path / "window_settings.json"

    monkeypatch.setattr(
        window_settings,
        "WINDOW_SETTINGS_FILE",
        path,
    )

    return path


def test_catalog_has_unique_ids() -> None:
    """У скинов уникальные идентификаторы и осмысленные описания."""

    ids = [skin.id for skin in skins.SKINS]

    assert ids == list(dict.fromkeys(ids))
    assert "terminal" in ids

    for skin in skins.SKINS:
        assert skin.name
        assert skin.tagline
        assert skin.description
        assert skin.palette.get("screen")
        assert skin.status in ("ready", "draft")


def test_skins_live_in_their_folders() -> None:
    """Каждый скин лежит в skins/<id>/ и имеет skin.json."""

    for skin in skins.SKINS:
        assert skin.folder.is_dir()
        assert skin.folder.name == skin.id
        assert (skin.folder / skins.SKIN_FILE).is_file()


def test_terminal_textures_are_inside_the_skin_folder() -> None:
    """Текстуры основного скина лежат рядом с его skin.json."""

    skin = skins.get_skin("terminal")

    for placeholder in skins.DEFAULT_TEXTURES:
        path = skin.texture_path(placeholder)

        assert path.is_file(), path
        assert path.parent == skin.folder


def test_style_uses_skin_textures() -> None:
    """QSS подставляет пути из папки скина."""

    from terminal.ui.window_style import build_window_style

    terminal = build_window_style("terminal")
    vault = build_window_style("vault")

    assert "skins/terminal" in terminal.replace("\\", "/")
    # У «Убежища» своих текстур пока нет — берутся базовые.
    assert "skins/terminal" in vault.replace("\\", "/")


def test_default_skin_is_terminal(settings_file) -> None:
    """Без настроек выбран «Терминал»."""

    assert skins.load_skin_id() == "terminal"
    assert skins.get_skin("unknown").id == "terminal"


def test_skin_choice_is_saved(settings_file) -> None:
    """Выбор скина переживает перезапуск."""

    assert skins.save_skin_id("vault") == "vault"
    assert skins.load_skin_id() == "vault"

    document = settings_file.read_text(encoding="utf-8")

    assert '"skin": "vault"' in document


def test_unknown_skin_falls_back(settings_file) -> None:
    """Неизвестный скин заменяется скином по умолчанию."""

    assert skins.save_skin_id("нет-такого") == "terminal"
    assert skins.load_skin_id() == "terminal"


def test_other_settings_survive_skin_change(settings_file) -> None:
    """Смена скина не трогает шрифт и модули."""

    window_settings.save_window_settings(
        {
            "chat_font_family": "Consolas",
            "chat_font_size": 13,
            "modules": {"internet": True},
            "skin": "terminal",
        }
    )

    skins.save_skin_id("vault")

    settings = window_settings.load_window_settings()

    assert settings["skin"] == "vault"
    assert settings["chat_font_family"] == "Consolas"
    assert settings["chat_font_size"] == 13
    assert settings["modules"]["internet"] is True
