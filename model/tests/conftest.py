# GiperionModel/tests/conftest.py                                      v001
# Тестовые данные модели: без зависимости от data/ приложения.

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _model_data(monkeypatch):
    """Подменяет файлы данных на минимальные фикстуры."""

    from giperion_model import neural_loader, personality_catalog

    monkeypatch.setattr(
        neural_loader,
        "INTENTS_FILE",
        FIXTURES / "intents.json",
    )
    monkeypatch.setattr(
        personality_catalog,
        "PERSONALITIES_FILE",
        FIXTURES / "personality_matrices.json",
    )
    monkeypatch.setattr(
        personality_catalog,
        "SETTINGS_FILE",
        FIXTURES / "personality_settings.json",
    )
