# Giperion/tests/test_ui_models_and_modules.py                     v005
# Проверки названий модулей, умений моделей и сената.
# Последнее изменение: аватарки моделей и их файлы.

from terminal.core.model_registry import get_model
from terminal.ui.panels_mixin import MODULE_INFO
from terminal.ui.value_text import model_skill_entries


def test_module_titles_and_empty_hints() -> None:
    """Модули называются по-новому, описания у всех убраны."""

    assert MODULE_INFO["internet"][0] == "Сетевой модуль"
    assert MODULE_INFO["voice"][0] == "Голосовой модуль"
    assert MODULE_INFO["conference"][0] == "Сенат"
    assert "files" not in MODULE_INFO
    assert all(hint == "" for _, hint in MODULE_INFO.values())


def test_model_skills_come_from_card() -> None:
    """Умения внешней модели берутся из её сильных сторон и функций."""

    model = get_model("deepseek-v4.1-flash-free")
    entries = model_skill_entries(model)
    names = [entry["name"] for entry in entries]

    assert model is not None
    assert "Текст" in names
    assert "Кодинг" in names
    assert "Изображения" in names
    assert all(entry["description"] for entry in entries)


def test_model_avatars_exist() -> None:
    """У каждой указанной аватарки модели есть файл в проекте."""

    from config import BASE_DIR
    from terminal.core.model_registry import load_models

    models = load_models()
    with_avatar = [
        model for model in models if model.get("avatar")
    ]

    assert with_avatar

    for model in with_avatar:
        path = BASE_DIR / model["avatar"]

        assert path.is_file(), f"{model['id']}: {model['avatar']}"

    deepseek = next(
        model
        for model in models
        if model["id"] == "deepseek-v4.1-flash-free"
    )

    assert deepseek["avatar"].endswith("deepseek_face.png")


def test_giperion_skills_are_honest() -> None:
    """У локального ядра показываются только реальные оценки карточки."""

    model = get_model("giperion")
    entries = model_skill_entries(model)
    names = [entry["name"] for entry in entries]

    assert model is not None
    assert "Текст" in names
    assert "Графика" not in names
    assert "Видео" not in names
