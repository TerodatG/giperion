# Giperion/tests/test_linear_intent_parity.py                         v001
# Чистый Python-роутер должен совпадать со sklearn на тех же весах.
# Последнее изменение: первый вариант — сверка предсказаний.

import pytest

sklearn = pytest.importorskip("sklearn")

from giperion_model.language.linear_intent import (  # noqa: E402
    LinearIntentRouter,
)
from tools.train_linear_intent import (  # noqa: E402
    export_router,
    fit_router,
)

TEXTS = [
    "кот спит",
    "кот ест",
    "кот мурчит",
    "пёс спит",
    "пёс ест",
    "пёс лает",
]
LABELS = ["cat", "cat", "cat", "dog", "dog", "dog"]


def test_router_matches_sklearn(tmp_path) -> None:
    """Артефакт и загрузчик повторяют предсказания sklearn."""

    vectorizer, model = fit_router(TEXTS, LABELS, 10.0)
    output = tmp_path / "router.json"

    export_router(
        vectorizer,
        model,
        output,
        top_weights=0,
        metrics={"top1": 1.0, "macro_f1": 1.0},
        train_size=len(TEXTS),
    )

    router = LinearIntentRouter.load(output)

    assert router is not None

    queries = ["кот", "пёс", "кот ест", "пёс лает", "спит"]
    expected = model.predict(vectorizer.transform(queries))
    actual = [router.predict(text)[0] for text in queries]

    assert actual == list(expected)
