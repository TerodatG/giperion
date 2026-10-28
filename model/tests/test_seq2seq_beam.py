# GiperionModel/tests/test_seq2seq_beam.py                            v001
# Beam search для генератора ответов.
# Последнее изменение: первый вариант — форма и batch-ограничение.

import pytest
import torch

from giperion_model.training.model_seq2seq import Seq2Seq, beam_rank


def make_model() -> Seq2Seq:
    """Создаёт маленькую необученную модель для проверки формы."""

    torch.manual_seed(0)

    return Seq2Seq(
        vocab_size=20,
        pad_id=0,
        sos_id=2,
        eos_id=3,
        embed_dim=8,
        hidden_size=16,
        attention_size=8,
    )


def test_beam_returns_one_sequence() -> None:
    """Beam search возвращает тензор (1, длина) в пределах словаря."""

    model = make_model()
    source = torch.tensor([[1, 4, 5]])
    mask = source == 0
    result = model.generate_beam(
        source,
        mask,
        max_len=6,
        beam_size=3,
    )

    assert result.shape[0] == 1
    assert 0 < result.shape[1] <= 6
    assert int(result.min()) >= 0
    assert int(result.max()) < 20


def test_beam_rejects_batch() -> None:
    """Beam search реализован только для одного примера."""

    model = make_model()

    with pytest.raises(ValueError):
        model.generate_beam(
            torch.tensor([[1, 4], [2, 5]]),
            torch.zeros((2, 2), dtype=torch.bool),
        )


def test_beam_rank_prefers_longer_confident_answer() -> None:
    """Нормировка по длине не даёт короткому лучу несправедливый перевес."""

    short = {"tokens": [1], "score": -1.0}
    long = {"tokens": [1, 2, 3, 4], "score": -1.2}

    assert beam_rank(long) > beam_rank(short)
