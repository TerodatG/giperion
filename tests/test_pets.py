# Giperion/tests/test_pets.py                                       v005
# Проверки дронов терминала: базовые, свои, закрепление и личность.
# Последнее изменение: удаление своего дрона.

from terminal.core import pets


def test_default_pets_are_available(tmp_path, monkeypatch) -> None:
    """Без файла доступны два дрона."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    loaded = pets.load_pets()

    assert [pet["id"] for pet in loaded] == [
        "cyber-spider",
        "robot-vacuum",
    ]
    assert loaded[0]["name"] == "Кибер паук"
    assert loaded[1]["name"] == "Робот пылесос"
    assert loaded[0]["custom"] is False


def test_nickname_can_be_changed(tmp_path, monkeypatch) -> None:
    """Кличка меняется, а имя вида и прогресс остаются прежними."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    updated = pets.set_pet_nickname("cyber-spider", "  Бублик  ")

    assert updated is not None
    assert updated["nickname"] == "Бублик"
    assert updated["name"] == "Кибер паук"

    loaded = {pet["id"]: pet for pet in pets.load_pets()}

    assert loaded["cyber-spider"]["nickname"] == "Бублик"
    assert loaded["cyber-spider"]["progress"]["level"] == 1
    assert loaded["robot-vacuum"]["nickname"] == ""


def test_empty_nickname_returns_to_name(tmp_path, monkeypatch) -> None:
    """Кличку можно стереть: по умолчанию её нет."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    pets.set_pet_nickname("robot-vacuum", "Мурка")
    updated = pets.set_pet_nickname("robot-vacuum", "   ")

    assert updated is not None
    assert updated["nickname"] == ""

    loaded = {pet["id"]: pet for pet in pets.load_pets()}

    assert loaded["robot-vacuum"]["nickname"] == ""


def test_unknown_pet_is_not_renamed(tmp_path, monkeypatch) -> None:
    """Несуществующего дрона переименовать нельзя."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    assert pets.set_pet_nickname("nobody", "Кто-то") is None
    assert not (tmp_path / "pets.json").exists()


def test_custom_pet_can_be_removed(tmp_path, monkeypatch) -> None:
    """Своего дрона можно удалить, базового — нельзя."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    custom = pets.add_custom_pet("Шарик", "spider")

    assert custom is not None
    assert pets.set_active_pet_id(custom["id"]) is True

    assert pets.remove_custom_pet(custom["id"]) is True
    assert pets.get_pet(custom["id"]) is None
    assert pets.get_active_pet_id() == ""

    # Базовые дроны остаются на месте.
    assert pets.remove_custom_pet("cyber-spider") is False
    assert pets.get_pet("cyber-spider") is not None


def test_custom_pet_copies_base_template(
    tmp_path,
    monkeypatch,
) -> None:
    """Свой дрон копирует базовый шаблон личности."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    pet = pets.add_custom_pet(
        "Бублик",
        "spider",
        "Любит спать на клавиатуре.",
    )

    assert pet is not None
    assert pet["id"] == "custom-1"
    assert pet["name"] == "Бублик"
    assert pet["species"] == "spider"
    assert pet["custom"] is True
    assert pet["base_model"] == "giperion"
    assert pet["traits"] == pets.BASE_TEMPLATE["traits"]

    loaded = pets.load_pets()

    assert [item["id"] for item in loaded] == [
        "cyber-spider",
        "robot-vacuum",
        "custom-1",
    ]


def test_active_pet_roundtrip(tmp_path, monkeypatch) -> None:
    """Закрепление дрона сохраняется и снимается."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    assert pets.get_active_pet() is None
    assert pets.set_active_pet_id("robot-vacuum") is True
    assert pets.get_active_pet_id() == "robot-vacuum"
    assert pets.get_active_pet()["name"] == "Робот пылесос"

    assert pets.set_active_pet_id("") is True
    assert pets.get_active_pet() is None
    assert pets.set_active_pet_id("unknown") is False


def test_pet_persona_answers_identity(
    tmp_path,
    monkeypatch,
) -> None:
    """На вопрос «кто ты» дрон отвечает своим именем."""

    from terminal.core.chatbot import get_response

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    pet = pets.get_pet("robot-vacuum")
    answer, save = get_response("кто ты", persona=pet)

    assert "Робот пылесос" in answer
    assert save is True


def test_pet_activity_updates_progress(
    tmp_path,
    monkeypatch,
) -> None:
    """Разговоры и новые фразы попадают в успехи обучения."""

    monkeypatch.setattr(
        pets,
        "PETS_FILE",
        tmp_path / "pets.json",
    )

    pets.set_active_pet_id("cyber-spider")
    updated = pets.record_pet_activity(
        "cyber-spider",
        learned=1,
    )

    assert updated is not None
    assert updated["progress"]["conversations"] == 1
    assert updated["progress"]["learned_phrases"] == 1
    assert updated["progress"]["experience"] == 10
    assert updated["progress"]["level"] == 1

    for _ in range(9):
        pets.record_pet_activity("cyber-spider")

    saved = pets.get_pet("cyber-spider")

    assert saved["progress"]["conversations"] == 10
    assert saved["progress"]["experience"] == 100
    assert saved["progress"]["level"] == 2
