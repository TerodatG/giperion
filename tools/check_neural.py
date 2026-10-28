# Giperion/tools/check_neural.py                                   v001
# Дымовой тест нейросети: диагноз классификатора и ответ бота.
# Последнее изменение: первый вариант.

from kraper_model.neural_engine import _build_engine
from terminal.core.chatbot import get_response

CASES = [
    "Привет!",
    "Какая погода сегодня?",
    "расскажи интересный факт",
    "ржачная тема есть?",
    "ну как сам?",
    "топ книг назови",
    "зарплата",
    "спасибо",
    "сколько будет 2+2",
    "люпапупу",
]


def main() -> None:
    """Печатает диагноз модели и итоговый ответ бота."""

    engine = _build_engine()

    if engine is None:
        print("Нейросеть не загрузилась.")

        return

    print(f"Устройство: {engine.device}")
    print()

    for text in CASES:
        label, confidence = engine.classify(text)
        neural = engine.reply(text)
        answer, _ = get_response(text)

        print(f">>> {text}")
        print(f"    намерение: {label} ({confidence:.2f})")
        print(f"    нейросеть: {neural or '—'}")
        print(f"    бот:       {answer}")
        print()


if __name__ == "__main__":
    main()
