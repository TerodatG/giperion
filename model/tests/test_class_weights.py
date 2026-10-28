# GiperionModel/tests/test_class_weights.py                           v001
# Веса классов для эксперимента с CNN.
# Последнее изменение: первый вариант — проверка баланса.

import torch

from giperion_model.training import train_charcnn


def test_unweighted_loss_by_default(monkeypatch) -> None:
    """Без флага loss обычный."""

    monkeypatch.setattr(train_charcnn, "BALANCED", False)

    criterion = train_charcnn.loss_function(
        ["a", "b"],
        [{"label": "a"}, {"label": "b"}],
    )

    assert criterion.weight is None


def test_balanced_loss_weights_rare_class(monkeypatch) -> None:
    """Редкий класс получает больший вес."""

    monkeypatch.setattr(train_charcnn, "BALANCED", True)

    criterion = train_charcnn.loss_function(
        ["a", "b"],
        [
            {"label": "a"},
            {"label": "a"},
            {"label": "a"},
            {"label": "b"},
        ],
    )

    weights = criterion.weight

    assert weights is not None
    assert torch.isclose(weights[0], torch.tensor(2 / 3))
    assert torch.isclose(weights[1], torch.tensor(2.0))
