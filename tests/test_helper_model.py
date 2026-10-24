# Giperion/tests/test_helper_model.py                                v001
# Проверки выбора внешней модели для помощи Гипериону.
# Последнее изменение: компаньоны, репутация и навык.

from terminal.core import helper_model


def make_model(
    model_id: str,
    name: str,
    skill: int,
    available: bool = True,
) -> dict:
    """Собирает минимальную карточку внешней модели для теста."""

    return {
        "id": model_id,
        "name": name,
        "available": available,
        "model_id": f"{model_id}-remote",
        "strengths": {"Текст": skill},
    }


def patch_models(
    monkeypatch,
    models: list[dict],
    requests: dict[str, int],
    companions: list[str] | None = None,
) -> None:
    """Подменяет каталог, статистику и список компаньонов."""

    monkeypatch.setattr(
        helper_model,
        "load_models",
        lambda: models,
    )
    monkeypatch.setattr(
        helper_model,
        "load_companion_ids",
        lambda: list(companions or []),
    )
    monkeypatch.setattr(
        helper_model,
        "get_reputation",
        lambda model_id: {
            "requests": requests.get(model_id, 0),
            "stars": 0,
            "percent": 0,
        },
    )


def test_companion_wins_over_higher_reputation(
    monkeypatch,
) -> None:
    """Отмеченный компаньон важнее модели с большей репутацией."""

    models = [
        make_model("deepseek", "DeepSeek", 4),
        make_model("qwen", "Qwen", 5),
    ]
    patch_models(
        monkeypatch,
        models,
        {"deepseek": 8, "qwen": 0},
        companions=["qwen"],
    )

    assert helper_model.get_helper_model()["id"] == "qwen"


def test_without_companions_rank_is_reputation_then_skill(
    monkeypatch,
) -> None:
    """Без компаньонов побеждает репутация, затем сумма навыков."""

    models = [
        make_model("first", "First", 1),
        make_model("skilled", "Skilled", 5),
        make_model("popular", "Popular", 2),
    ]
    patch_models(
        monkeypatch,
        models,
        {"first": 5, "skilled": 5, "popular": 2},
    )

    assert helper_model.get_helper_model()["id"] == "skilled"


def test_unavailable_companion_is_skipped(
    monkeypatch,
) -> None:
    """Отключённый компаньон не мешает выбрать доступную модель."""

    models = [
        make_model("offline", "Offline", 5, available=False),
        make_model("online", "Online", 1),
    ]
    patch_models(
        monkeypatch,
        models,
        {"offline": 100, "online": 1},
        companions=["offline"],
    )

    assert helper_model.get_helper_model()["id"] == "online"


def test_no_external_models_gives_none(
    monkeypatch,
) -> None:
    """Если внешних моделей нет, помощь недоступна."""

    patch_models(monkeypatch, [], {})

    assert helper_model.get_helper_model() is None
