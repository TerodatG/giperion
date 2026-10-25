# Giperion/tests/test_pets.py                                       v001
# Проверки питомцев терминала: базовые, свои, закрепление и личность.

from terminal.core import pets


def test_default_pets_are_available(tmp_path, monkeypatch) -> None:
    """Без файла доступны робо-щенок и робо-кошка."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    loaded = pets.load_pets()

    assert [pet["id"] for pet in loaded] == [
        "robot-puppy",
        "robot-cat",
    ]
    assert loaded[0]["name"] == "Робо-щенок"
    assert loaded[1]["name"] == "Робо-кошка"
    assert loaded[0]["custom"] is False


def test_custom_pet_copies_base_template(
    tmp_path,
    monkeypatch,
) -> None:
    """Свой питомец копирует базовый шаблон личности."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    pet = pets.add_custom_pet(
        "Бублик",
        "cat",
        "Любит спать на клавиатуре.",
    )

    assert pet is not None
    assert pet["id"] == "custom-1"
    assert pet["name"] == "Бублик"
    assert pet["species"] == "cat"
    assert pet["custom"] is True
    assert pet["base_model"] == "giperion"
    assert pet["traits"] == pets.BASE_TEMPLATE["traits"]

    loaded = pets.load_pets()

    assert [item["id"] for item in loaded] == [
        "robot-puppy",
        "robot-cat",
        "custom-1",
    ]


def test_active_pet_roundtrip(tmp_path, monkeypatch) -> None:
    """Закрепление питомца сохраняется и снимается."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    assert pets.get_active_pet() is None
    assert pets.set_active_pet_id("robot-cat") is True
    assert pets.get_active_pet_id() == "robot-cat"
    assert pets.get_active_pet()["name"] == "Робо-кошка"

    assert pets.set_active_pet_id("") is True
    assert pets.get_active_pet() is None
    assert pets.set_active_pet_id("unknown") is False


def test_pet_persona_answers_identity(
    tmp_path,
    monkeypatch,
) -> None:
    """На вопрос «кто ты» питомец отвечает своим именем."""

    from terminal.core.chatbot import get_response

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    pet = pets.get_pet("robot-cat")
    answer, save = get_response("кто ты", persona=pet)

    assert "Робо-кошка" in answer
    assert save is True
