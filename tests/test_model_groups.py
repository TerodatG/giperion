# Giperion/tests/test_model_groups.py                               v002
# Включение групп моделей: бесплатные, Go и их последствия.
# Последнее изменение: недоступность личных моделей без канала.

import pytest

from terminal.core import model_files, model_settings
from terminal.core.model_catalog import (
    COMPANION_GROUP,
    CONFERENCE_GROUP,
    DEFAULT_MODEL_ID,
)

FREE_ID = "deepseek-v4.1-flash-free"
GO_ID = "go-deepseek-v4.1-flash"


@pytest.fixture()
def settings_file(tmp_path, monkeypatch):
    """Изолирует файл настроек моделей."""

    path = tmp_path / "model_settings.json"

    monkeypatch.setattr(model_files, "SETTINGS_FILE", path)

    return path


def test_groups_are_enabled_by_default(settings_file) -> None:
    """Без файла настроек обе группы включены."""

    assert model_settings.load_model_group_flags() == {
        "free": True,
        "go": True,
    }


def test_group_can_be_disabled(settings_file) -> None:
    """Выключение группы сохраняется между открытиями окна."""

    assert model_settings.set_model_group_enabled("go", False)
    assert model_settings.load_model_group_flags()["go"] is False

    assert model_settings.set_model_group_enabled("go", True)
    assert model_settings.load_model_group_flags()["go"] is True


def test_unknown_group_is_rejected(settings_file) -> None:
    """Неизвестную группу выключить нельзя."""

    assert model_settings.set_model_group_enabled("own", False) is False


def test_model_group_key() -> None:
    """Модели делятся на бесплатные, Go и ядро."""

    assert model_settings.model_group_key({"api": "opencode"}) == "free"
    assert model_settings.model_group_key(
        {"api": "opencode-go"}
    ) == "go"
    assert model_settings.model_group_key({"api": "local"}) == "core"
    assert model_settings.model_group_key({"api": ""}) == "core"


def test_disabled_model_cannot_be_activated(settings_file) -> None:
    """Модель выключенной группы не становится активной."""

    model_settings.set_model_group_enabled("go", False)

    assert model_settings.set_current_model_id(GO_ID) is False
    assert model_settings.get_current_model_id() == DEFAULT_MODEL_ID

    assert model_settings.set_current_model_id(FREE_ID) is True
    assert model_settings.get_current_model_id() == FREE_ID


def test_active_model_falls_back_when_group_disabled(
    settings_file,
) -> None:
    """Выключение группы возвращает Гипериона вместо её модели."""

    assert model_settings.set_current_model_id(GO_ID) is True
    assert model_settings.get_current_model_id() == GO_ID

    model_settings.set_model_group_enabled("go", False)

    assert model_settings.get_current_model_id() == DEFAULT_MODEL_ID


def test_companions_hide_disabled_group(settings_file) -> None:
    """Модели выключенной группы исчезают из компаньонов."""

    assert model_settings.set_companion(GO_ID, True)
    assert GO_ID in model_settings.load_companion_ids()

    model_settings.set_model_group_enabled("go", False)

    assert GO_ID not in model_settings.load_companion_ids()

    visible = {
        model["id"]
        for model in model_settings.get_models_by_group(COMPANION_GROUP)
    }

    assert GO_ID not in visible


def test_conference_hides_disabled_group(settings_file) -> None:
    """Модели выключенной группы исчезают из сената."""

    assert model_settings.set_conference_member(GO_ID, True)
    assert GO_ID in model_settings.load_conference_ids()

    model_settings.set_model_group_enabled("go", False)

    assert GO_ID not in model_settings.load_conference_ids()

    visible = {
        model["id"]
        for model in model_settings.get_models_by_group(CONFERENCE_GROUP)
    }

    assert GO_ID not in visible


def test_choice_returns_after_group_enabled(settings_file) -> None:
    """Сохранённый выбор не теряется: включил группу — модель вернулась."""

    model_settings.set_companion(GO_ID, True)
    model_settings.set_conference_member(GO_ID, True)

    model_settings.set_model_group_enabled("go", False)
    model_settings.set_model_group_enabled("go", True)

    assert GO_ID in model_settings.load_companion_ids()
    assert GO_ID in model_settings.load_conference_ids()


def test_core_models_are_always_enabled(settings_file) -> None:
    """Гиперион и свои модели не зависят от групп."""

    model_settings.set_model_group_enabled("free", False)
    model_settings.set_model_group_enabled("go", False)

    assert model_settings.set_current_model_id(DEFAULT_MODEL_ID) is True
    assert model_settings.get_current_model_id() == DEFAULT_MODEL_ID

    free = next(
        model
        for model in model_settings.load_models()
        if model["id"] == FREE_ID
    )

    assert model_settings.model_group_key(free) == "free"
    assert model_settings.is_model_enabled(free) is False


def test_core_model_has_channel(settings_file) -> None:
    """У локального ядра канал есть всегда."""

    model = model_settings.get_model(DEFAULT_MODEL_ID)

    assert model is not None
    assert model_settings.model_has_channel(model) is True
    assert model_settings.is_model_usable(model) is True


def test_personal_model_without_channel_is_unusable(
    settings_file,
    tmp_path,
    monkeypatch,
) -> None:
    """Своя модель без канала недоступна, даже если группа включена."""

    from terminal.core import model_custom

    monkeypatch.setattr(
        model_files,
        "CUSTOM_MODELS_FILE",
        tmp_path / "custom_models.json",
    )

    pet = model_custom.add_custom_model("Локальная", "Local")

    assert pet is not None

    model = model_settings.get_model(pet["id"])

    assert model is not None
    assert model_settings.model_has_channel(model) is False
    assert model_settings.is_model_enabled(model) is True
    assert model_settings.is_model_usable(model) is False

    assert model_settings.set_current_model_id(pet["id"]) is False
    assert model_settings.get_current_model_id() == DEFAULT_MODEL_ID

    assert model_settings.set_companion(pet["id"], True) is False
    assert model_settings.set_conference_member(
        pet["id"],
        True,
    ) is False


def test_unusable_personal_model_leaves_lists(
    settings_file,
    tmp_path,
    monkeypatch,
) -> None:
    """Если своя модель уже была в списках, она из них исчезает."""

    from shared.storage.json_store import write_json
    from terminal.core import model_custom

    monkeypatch.setattr(
        model_files,
        "CUSTOM_MODELS_FILE",
        tmp_path / "custom_models.json",
    )

    pet = model_custom.add_custom_model("Локальная", "Local")

    assert pet is not None

    # Имитируем старые настройки, где модель уже была участником.
    write_json(
        model_files.SETTINGS_FILE,
        {
            "companions": [pet["id"]],
            "conference": [pet["id"]],
            "model_groups": {"free": True, "go": True},
        },
    )

    assert model_settings.load_companion_ids() == []
    assert model_settings.load_conference_ids() == []
