# Giperion/tests/test_answer_job.py                                v001
# Проверка передачи скрытой истории в фоновый расчёт ответа.

from terminal.ui import answer_job


def test_answer_job_passes_context(monkeypatch) -> None:
    """Контекст доходит до движка модели из фонового потока."""

    captured = []

    def fake_response(text, context):
        captured.append((text, context))

        return ("ответ", True)

    monkeypatch.setattr(
        answer_job,
        "get_model_response",
        fake_response,
    )

    job = answer_job.AnswerJob("вопрос", "Пользователь: раньше")
    job._thread.join(timeout=2)

    assert job.done
    assert captured == [
        ("вопрос", "Пользователь: раньше"),
    ]
