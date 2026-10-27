# GiperionModel/tests/test_linear_intent.py                            v001
# Линейный роутер: n-граммы, загрузка артефакта и предсказание.
# Последнее изменение: первый вариант — без sklearn.

import json
from pathlib import Path

from giperion_model.language.linear_intent import (
    LinearIntentRouter,
    char_wb_ngrams,
)


def write_artifact(path: Path, **overrides) -> Path:
    """Пишет минимальный корректный артефакт."""

    document = {
        "labels": ["first", "second"],
        "vocabulary": [
            " ab",
            "ab ",
            " ab ",
            " xy",
            "xy ",
            " xy ",
        ],
        "idf": [1.0] * 6,
        "intercept": [0.0, 0.0],
        "weights": [
            [[0, 2.0]],
            [[3, 2.0]],
        ],
    }
    document.update(overrides)
    path.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )

    return path


def test_char_wb_ngrams_match_sklearn_layout() -> None:
    """Пробелы по краям слова — как у char_wb."""

    assert char_wb_ngrams("ab") == [" ab", "ab ", " ab "]
    assert char_wb_ngrams("") == []
    assert char_wb_ngrams("ab cd") == [
        " ab",
        "ab ",
        " ab ",
        " cd",
        "cd ",
        " cd ",
    ]


def test_missing_artifact_is_silent(tmp_path) -> None:
    """Без файла роутер просто не загружается."""

    assert LinearIntentRouter.load(tmp_path / "none.json") is None


def test_router_predicts_by_ngram(tmp_path) -> None:
    """Класс выбирается по самому весомому n-грамму."""

    router = LinearIntentRouter.load(
        write_artifact(tmp_path / "router.json")
    )

    assert router is not None
    assert router.predict("ab")[0] == "first"
    assert router.predict("xy")[0] == "second"
    assert router.predict("zz") is None
    assert router.predict("") is None


def test_broken_artifact_is_rejected(tmp_path) -> None:
    """Повреждённый JSON не должен ронять загрузку."""

    path = tmp_path / "broken.json"
    path.write_text("{не json", encoding="utf-8")

    assert LinearIntentRouter.load(path) is None

    incomplete = write_artifact(
        tmp_path / "incomplete.json",
        idf=[1.0],
    )

    assert LinearIntentRouter.load(incomplete) is None
