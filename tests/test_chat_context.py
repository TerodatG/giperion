# Giperion/tests/test_chat_context.py                              v001
# Проверки скрытой выжимки чата и запроса внешней модели с историей.

from terminal.core import chat_context
from terminal.core.model_engine import build_external_prompt


def sample_log() -> list:
    return [
        ("system", "Гиперион запущен", "01.01.2026 10:00"),
        ("user", "Привет", "01.01.2026 10:01"),
        (
            "bot",
            "Здравствуй",
            True,
            "01.01.2026 10:01",
            "Гиперион",
            "bot",
        ),
        ("system", "История очищена", "01.01.2026 10:02"),
        ("level", 2, "Новичок"),
        (
            "bot",
            "Продолжим",
            False,
            "01.01.2026 10:03",
            "DeepSeek",
            "bot",
        ),
    ]


def test_summary_has_only_user_and_models() -> None:
    """Системные сообщения и плашки уровня не попадают в выжимку."""

    summary = chat_context.build_chat_summary(sample_log())

    assert "Пользователь: Привет" in summary
    assert "Гиперион: Здравствуй" in summary
    assert "DeepSeek: Продолжим" in summary
    assert "СИСТЕМА" not in summary
    assert "История очищена" not in summary
    assert "Новичок" not in summary


def test_summary_is_trimmed() -> None:
    """Слишком длинная история сохраняет последнюю часть."""

    log = [
        ("user", f"вопрос {index} " + "x" * 50, "")
        for index in range(500)
    ]

    summary = chat_context.build_chat_summary(log, max_chars=500)

    assert "начало диалога сокращено" in summary
    assert "вопрос 499" in summary


def test_context_file_roundtrip(tmp_path) -> None:
    """Файл выжимки записывается и читается."""

    path = chat_context.write_chat_context(
        "chat_test",
        "Тестовый чат",
        sample_log(),
        directory=tmp_path,
    )

    text = chat_context.read_chat_context(
        "chat_test",
        directory=tmp_path,
    )

    assert path.exists()
    assert "Контекст чата «Тестовый чат»" in text
    assert "Пользователь: Привет" in text

    chat_context.remove_chat_context(
        "chat_test",
        directory=tmp_path,
    )

    assert not path.exists()


def test_external_prompt_includes_context() -> None:
    """Внешняя модель получает историю и текущую реплику."""

    prompt = build_external_prompt(
        "DeepSeek",
        "Что дальше?",
        "Пользователь: Привет\n\nГиперион: Здравствуй",
    )

    assert "история этого чата" in prompt
    assert "Пользователь: Привет" in prompt
    assert "Пользователь: Что дальше?" in prompt


def test_external_prompt_without_context() -> None:
    """Пустая история не добавляет лишний блок."""

    prompt = build_external_prompt("DeepSeek", "Привет")

    assert "история этого чата" not in prompt
    assert "Пользователь: Привет" in prompt


def test_external_prompt_forbids_self_intro() -> None:
    """Внешняя модель не должна представляться в каждом ответе."""

    prompt = build_external_prompt("DeepSeek", "Привет")

    assert "Не представляйся" in prompt
    assert "Представляйся своим именем" not in prompt
    assert "Я — …" in prompt


def test_model_response_passes_history(monkeypatch) -> None:
    """История доходит до внешней модели через движок."""

    from terminal.core import model_engine

    captured = {}

    def fake_ask(model_id, text, provider_id, title):
        captured["text"] = text

        return ("ответ", {"total": 3})

    monkeypatch.setattr(
        model_engine,
        "get_current_model_id",
        lambda: "deepseek",
    )
    monkeypatch.setattr(
        model_engine,
        "get_model",
        lambda model_id: {
            "name": "DeepSeek",
            "available": True,
            "model_id": "deepseek-test",
            "provider_id": "opencode",
        },
    )
    monkeypatch.setattr(
        model_engine,
        "record_model_request",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(model_engine, "ask_model", fake_ask)

    answer, save = model_engine.get_model_response(
        "Что дальше?",
        "Пользователь: Привет",
    )

    assert answer == "ответ"
    assert save is True
    assert "Пользователь: Привет" in captured["text"]
    assert "Пользователь: Что дальше?" in captured["text"]

