# Giperion/tests/test_label_unknown.py                                v001
# Подсказки для накопителя непонятых фраз.
# Последнее изменение: первый вариант — общий порог модели.

from shared.text_tools import normalize_message
from tools.label_unknown import suggest_action


class FakeEngine:
    """Минимальный движок для проверки подсказок."""

    def __init__(self, gated, guess) -> None:
        self.gated = gated
        self.guess = guess

    def _gated_classification(self, text):
        return self.gated

    def classify(self, text):
        return self.guess


def test_exact_pattern_is_marked_for_removal() -> None:
    """Фраза, уже известная по паттерну, — мусор в накопителе."""

    index = {normalize_message("привет"): "greeting"}
    action, tag, _note = suggest_action(
        "привет",
        index,
        None,
    )

    assert action == "trash"
    assert tag is None


def test_confident_router_suggests_category() -> None:
    """Уверенный ответ модели предлагается добавить."""

    engine = FakeEngine(
        gated=("greeting", 0.9),
        guess=("greeting", 0.9),
    )
    action, tag, _note = suggest_action(
        "здорово",
        {},
        engine,
    )

    assert action == "add"
    assert tag == "greeting"


def test_uncertain_model_requires_manual_label() -> None:
    """Ниже порога модель только подсказывает тег, но не решает."""

    engine = FakeEngine(
        gated=None,
        guess=("joke", 0.2),
    )
    action, tag, note = suggest_action(
        "непонятная фраза",
        {},
        engine,
    )

    assert action == "skip"
    assert tag is None
    assert "0.20" in note


def test_missing_engine_skips() -> None:
    """Без нейросети фраза остаётся на ручную разметку."""

    action, tag, _note = suggest_action("что-то", {}, None)

    assert action == "skip"
    assert tag is None
