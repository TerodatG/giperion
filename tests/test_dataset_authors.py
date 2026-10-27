# Giperion/tests/test_dataset_authors.py                           v001
# Проверки авторства ответов в истории и отбора пар для обучения.
# Последнее изменение: внешние модели не попадают в датасет Гипериона.

import json

from giperion_model.training import build_dataset
from terminal.memory import memory


def test_add_message_remembers_model(
    tmp_path,
    monkeypatch,
) -> None:
    """Ответ модели сохраняется вместе с её идентификатором."""

    path = tmp_path / "conversations.json"
    monkeypatch.setattr(memory, "CONVERSATIONS_FILE", path)

    memory.add_message("user", "привет")
    memory.add_message(
        "assistant",
        "ответ",
        model="deepseek-v4.1-flash-free",
    )

    records = json.loads(path.read_text(encoding="utf-8"))

    assert "model" not in records[0]
    assert records[1]["model"] == "deepseek-v4.1-flash-free"


def test_dataset_skips_foreign_model_answers(
    tmp_path,
    monkeypatch,
) -> None:
    """Генеративная модель учится только на ответах Гипериона."""

    path = tmp_path / "conversations.json"
    path.write_text(
        json.dumps(
            [
                {"role": "user", "text": "вопрос"},
                {"role": "assistant", "text": "ответ Гипериона"},
                {"role": "user", "text": "кто ты"},
                {
                    "role": "assistant",
                    "text": "я DeepSeek",
                    "model": "deepseek-v4.1-flash-free",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        build_dataset,
        "CONVERSATIONS_FILE",
        path,
    )

    pairs = {}
    added, skipped = build_dataset.build_conversation_pairs(pairs)

    assert added == 1
    assert skipped == 1
    assert [pair["input"] for pair in pairs.values()] == ["вопрос"]
