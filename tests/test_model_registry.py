# Giperion/tests/test_model_registry.py                            v010
# Проверки каталога, активации, репутации, токенов, своих моделей и компаньонов.
# Последнее изменение: удаление своей модели из каталога.

import json

import pytest

from terminal.core import model_files, model_registry


@pytest.fixture
def isolated_registry(
    tmp_path,
    monkeypatch,
):
    """Создаёт временный каталог, свои модели, выбор и статистику."""

    models_file = tmp_path / "models.json"
    custom_file = tmp_path / "custom_models.json"
    settings_file = tmp_path / "model_settings.json"
    stats_file = tmp_path / "model_stats.json"

    document = {
        "_meta": {"version": "v002"},
        "models": [
            {
                "id": "deepseek",
                "name": "DeepSeek",
                "provider": "OpenCode",
                "description": "Внешняя модель",
                "available": False,
                "group": "other",
                "avatar": "",
                "url": "https://example.org",
                "api": "opencode",
                "price": "бесплатно",
                "model_id": "deepseek-v4.1-flash-free",
                "provider_id": "opencode",
                "context_limit": 1000,
                "token_budget": 500,
                "strengths": {"Текст": 5, "Кодинг": 4},
                "capabilities": {
                    "reasoning": True,
                    "tool_call": True,
                    "modalities": {
                        "input": ["text", "image"],
                        "output": ["text"],
                    },
                    "limit": {"context": 1000, "output": 100},
                    "status": "active",
                },
            },
            {
                "id": "giperion",
                "name": "Гиперион",
                "provider": "ядро проекта",
                "description": "Своё ядро",
                "available": True,
                "group": "popular",
                "avatar": "",
                "url": "",
                "api": "local",
                "context_limit": 32,
                "token_budget": 1000,
                "strengths": {"Текст": 3},
            },
        ],
    }

    models_file.write_text(
        json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        model_files,
        "MODELS_FILE",
        models_file,
    )
    monkeypatch.setattr(
        model_files,
        "CUSTOM_MODELS_FILE",
        custom_file,
    )
    monkeypatch.setattr(
        model_files,
        "SETTINGS_FILE",
        settings_file,
    )
    monkeypatch.setattr(
        model_files,
        "STATS_FILE",
        stats_file,
    )

    return settings_file


def test_giperion_always_first(
    isolated_registry,
) -> None:
    """В списке первым идёт Гиперион, даже если в файле он второй."""

    models = model_registry.load_models()

    assert [
        model["id"]
        for model in models
    ] == ["giperion", "deepseek"]


def test_custom_model_can_be_removed(isolated_registry) -> None:
    """Своя модель добавляется и удаляется из каталога."""

    created = model_registry.add_custom_model("Qwen 3", "Alibaba")

    assert created is not None

    ids = [
        model["id"] for model in model_registry.load_models()
    ]

    assert created["id"] in ids

    assert model_registry.remove_custom_model(created["id"]) is True

    ids = [
        model["id"] for model in model_registry.load_models()
    ]

    assert created["id"] not in ids

    # Повторное удаление ничего не ломает.
    assert model_registry.remove_custom_model(created["id"]) is False


def test_capabilities_are_loaded_for_card(
    isolated_registry,
) -> None:
    """Функции модели не теряются при разборе каталога."""

    models = model_registry.load_models()
    deepseek = next(
        model for model in models if model["id"] == "deepseek"
    )

    assert deepseek["capabilities"]["reasoning"] is True
    assert deepseek["capabilities"]["modalities"]["input"] == [
        "text",
        "image",
    ]
    assert deepseek["capabilities"]["limit"]["context"] == 1000


def test_current_model_defaults_to_giperion(
    isolated_registry,
) -> None:
    """Без памяти о выборе активна модель по умолчанию."""

    assert (
        model_registry.get_current_model_id()
        == "giperion"
    )


def test_external_model_can_be_activated(
    isolated_registry,
) -> None:
    """Внешнюю модель можно активировать, даже если канал не настроен."""

    assert (
        model_registry.set_current_model_id("deepseek")
        is True
    )
    assert (
        model_registry.get_current_model_id()
        == "deepseek"
    )


def test_unknown_model_cannot_be_selected(
    isolated_registry,
) -> None:
    """Неизвестную модель выбрать нельзя."""

    assert (
        model_registry.set_current_model_id("nope")
        is False
    )


def test_companions_are_saved_and_listed(
    isolated_registry,
) -> None:
    """Компаньон попадает в закладку и переживает смену активной модели."""

    assert model_registry.set_companion("deepseek") is True
    assert model_registry.load_companion_ids() == ["deepseek"]
    assert model_registry.is_companion("deepseek") is True

    assert [
        model["id"]
        for model in model_registry.get_models_by_group(
            "companions"
        )
    ] == ["deepseek"]

    assert model_registry.set_current_model_id("giperion") is True
    assert model_registry.load_companion_ids() == ["deepseek"]

    assert model_registry.set_companion("deepseek", False) is True
    assert model_registry.load_companion_ids() == []
    assert model_registry.get_models_by_group("companions") == []


def test_giperion_can_be_companion(
    isolated_registry,
) -> None:
    """Гипериона тоже можно отметить компаньоном — как любую модель."""

    assert model_registry.set_companion("giperion") is True
    assert model_registry.load_companion_ids() == ["giperion"]
    assert model_registry.is_companion("giperion") is True

    assert [
        model["id"]
        for model in model_registry.get_models_by_group(
            "companions"
        )
    ] == ["giperion"]


def test_conference_members_are_saved_and_listed(
    isolated_registry,
) -> None:
    """Участник сената попадает на свою закладку."""

    assert model_registry.set_conference_member("deepseek") is True
    assert model_registry.load_conference_ids() == ["deepseek"]
    assert model_registry.is_conference_member("deepseek") is True

    assert [
        model["id"]
        for model in model_registry.get_models_by_group(
            "conference"
        )
    ] == ["deepseek"]

    assert model_registry.set_conference_member("giperion") is True
    assert model_registry.load_conference_ids() == [
        "deepseek",
        "giperion",
    ]

    assert model_registry.set_conference_member(
        "deepseek",
        False,
    ) is True
    assert model_registry.load_conference_ids() == ["giperion"]


def test_conference_tab_is_first() -> None:
    """Закладка «Сенат» стоит перед остальными."""

    assert model_registry.MODEL_GROUPS[0] == (
        "conference",
        "Сенат",
    )


def test_reputation_counts_requests(
    isolated_registry,
) -> None:
    """Обращения считаются, шкала считается от самой частой модели."""

    empty = model_registry.get_reputation("giperion")

    assert empty == {
        "requests": 0,
        "stars": 0,
        "percent": 0,
    }

    model_registry.record_model_request("giperion")
    model_registry.record_model_request("deepseek")
    model_registry.record_model_request("giperion")

    leader = model_registry.get_reputation("giperion")

    assert leader == {
        "requests": 2,
        "stars": 5,
        "percent": 100,
    }

    other = model_registry.get_reputation("deepseek")

    assert other == {
        "requests": 1,
        "stars": 3,
        "percent": 50,
    }


def test_tokens_are_counted(
    isolated_registry,
) -> None:
    """Токены копятся в статистике и попадают в расход модели."""

    model_registry.record_model_request("giperion", 300)

    usage = model_registry.get_usage("giperion")

    assert usage == {
        "context_limit": 32,
        "token_budget": 1000,
        "tokens_used": 300,
        "tokens_available": 700,
        "percent": 30,
    }


def test_stars_scale_is_five(
    isolated_registry,
) -> None:
    """Рисунок шкалы — всегда пять звёзд: заполненные и пустые."""

    assert model_registry.build_stars(0) == "☆☆☆☆☆"
    assert model_registry.build_stars(3) == "★★★☆☆"
    assert model_registry.build_stars(5) == "★★★★★"


def test_custom_model_is_added(
    isolated_registry,
) -> None:
    """Своя модель попадает в каталог и на закладку «Свои»."""

    model = model_registry.add_custom_model(
        "  Qwen   3  ",
        "Alibaba",
        "https://qwen.ai",
        "Своя модель",
        64000,
        500000,
    )

    assert model is not None
    assert model["id"] == "custom-1"
    assert model["name"] == "Qwen 3"
    assert model["group"] == "own"
    assert model["context_limit"] == 64000

    own_models = model_registry.get_models_by_group("own")

    assert [item["id"] for item in own_models] == ["custom-1"]


def test_custom_model_needs_name(
    isolated_registry,
) -> None:
    """Без названия своя модель не добавляется."""

    assert model_registry.add_custom_model("   ") is None


def test_external_model_keeps_opencode_ids(
    isolated_registry,
) -> None:
    """Внешняя модель хранит идентификаторы для локального сервиса."""

    model = model_registry.get_model("deepseek")

    assert model["model_id"] == "deepseek-v4.1-flash-free"
    assert model["provider_id"] == "opencode"


def test_region_blocked_models_are_hidden(
    tmp_path,
    monkeypatch,
) -> None:
    """Модели, недоступные в России, не попадают в список."""

    models_file = tmp_path / "models.json"
    custom_file = tmp_path / "custom_models.json"

    models_file.write_text(
        json.dumps(
            {
                "models": [
                    {
                        "id": "giperion",
                        "name": "Гиперион",
                        "available": True,
                        "group": "popular",
                    },
                    {
                        "id": "go-beam-free",
                        "name": "Beam Free (Go)",
                        "model_id": "beam-free",
                        "provider_id": "opencode-go",
                    },
                    {
                        "id": "go-grok-4.7",
                        "name": "Grok 4.7 (Go)",
                        "model_id": "grok-4.7",
                        "provider_id": "opencode-go",
                    },
                    {
                        "id": "go-deepseek-v4.1-flash",
                        "name": "DeepSeek V4.1 Flash (Go)",
                        "nickname": "DeepSeek Flash",
                        "model_id": "deepseek-v4.1-flash",
                        "provider_id": "opencode-go",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        model_files,
        "MODELS_FILE",
        models_file,
    )
    monkeypatch.setattr(
        model_files,
        "CUSTOM_MODELS_FILE",
        custom_file,
    )

    ids = [
        model["id"] for model in model_registry.load_models()
    ]

    assert "go-beam-free" not in ids
    assert "go-grok-4.7" not in ids
    assert "go-deepseek-v4.1-flash" in ids

    model = model_registry.get_model("go-deepseek-v4.1-flash")

    assert model["nickname"] == "DeepSeek Flash"
