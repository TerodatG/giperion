# GiperionModel/tests/test_config.py                                   v001
# Пути модели: пустые переменные окружения не должны вести в cwd.

from pathlib import Path

from giperion_model import config


def test_empty_env_falls_back(monkeypatch, tmp_path) -> None:
    """Пустой env-путь заменяется значением по умолчанию."""

    monkeypatch.setenv("GIPERION_TEST_PATH", "")

    assert config._path("GIPERION_TEST_PATH", tmp_path) == (
        tmp_path.resolve()
    )


def test_env_path_wins(monkeypatch, tmp_path) -> None:
    """Непустой env-путь имеет приоритет."""

    target = tmp_path / "custom"
    monkeypatch.setenv("GIPERION_TEST_PATH", str(target))

    assert config._path("GIPERION_TEST_PATH", tmp_path) == (
        target.resolve()
    )


def test_module_paths_are_absolute() -> None:
    """Основные каталоги модели всегда абсолютные."""

    for value in (
        config.BASE_DIR,
        config.DATA_DIR,
        config.MODELS_DIR,
        config.LOGS_DIR,
    ):
        assert isinstance(value, Path)
        assert value.is_absolute()
