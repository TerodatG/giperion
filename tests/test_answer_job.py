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


def test_pet_answer_uses_local_core(monkeypatch) -> None:
    """Питомец отвечает локальным ядром со своей личностью."""

    captured = {}

    def fake_response(text, persona=None, is_system_mode=False):
        captured["text"] = text
        captured["persona"] = persona

        return ("ответ питомца", True)

    monkeypatch.setattr(
        answer_job,
        "get_response",
        fake_response,
    )

    persona = {"name": "Робо-щенок"}

    job = answer_job.AnswerJob(
        "привет",
        local_only=True,
        persona=persona,
    )
    job._thread.join(timeout=2)

    assert job.done
    assert job.answer == "ответ питомца"
    assert job.save_to_history is True
    assert captured == {
        "text": "привет",
        "persona": persona,
    }
