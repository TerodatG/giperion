# Giperion/tests/test_train_seq2seq.py                                v001
# Подготовка пар для генератора.
# Последнее изменение: один ответ на вход.

from kraper_model.training.train_seq2seq import (
    one_response_per_input,
)


def test_one_response_per_input() -> None:
    """На каждый вопрос остаётся ровно один ответ."""

    pairs = [
        {"input": "привет", "output": "здравствуй"},
        {"input": "привет", "output": "привет"},
        {"input": "как дела", "output": "хорошо"},
    ]
    result = one_response_per_input(pairs)

    assert len(result) == 2
    assert len({pair["input"] for pair in result}) == 2
    assert {pair["input"] for pair in result} == {
        "привет",
        "как дела",
    }
