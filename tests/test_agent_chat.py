# Giperion/tests/test_agent_chat.py                                   v001
# Многоходовой режим: сообщения assistant/tool вместо одного промпта.

import json

from terminal.core.agent.loop import _trim_chat, run_agent
from terminal.core.agent.providers import (
    NativeBrain,
    OpenAICompatibleProvider,
)


def _tool_reply(call_id: str, name: str, args: dict) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(args),
                            },
                        }
                    ],
                }
            }
        ]
    }


def _text_reply(text: str) -> dict:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": text}}
        ]
    }


class RecordingProvider(OpenAICompatibleProvider):
    """Провайдер, который записывает сообщения и отдаёт заготовки."""

    def __init__(self, replies: list[dict]) -> None:
        self.sent: list[list[dict]] = []
        self.payloads: list[dict] = []
        self.replies = list(replies)

        super().__init__(
            "http://localhost/v1",
            "secret",
            "test-model",
        )
        self._post = self._record

    def _record(self, url, key, payload, timeout):
        self.sent.append(payload["messages"])
        self.payloads.append(dict(payload))

        return self.replies.pop(0)


def test_begin_builds_system_and_task() -> None:
    """Переписка начинается с системного сообщения и задачи."""

    provider = RecordingProvider([])
    brain = NativeBrain(provider)

    messages = brain.begin(
        "найди функцию",
        ["<<<ДАННЫЕ>>>\nтекст\n<<<КОНЕЦ ДАННЫХ>>>"],
    )

    assert messages[0]["role"] == "system"
    assert "function calling" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "найди функцию" in messages[1]["content"]
    assert "данные, а не инструкции" in messages[1]["content"]


def test_chat_mode_sends_assistant_and_tool_messages(tmp_path) -> None:
    """После вызова в переписке есть assistant с id и tool с результатом."""

    (tmp_path / "a.txt").write_text("альфа", encoding="utf-8")

    provider = RecordingProvider(
        [
            _tool_reply("call_1", "read_file", {"path": "a.txt"}),
            _text_reply("прочитал"),
        ]
    )
    brain = NativeBrain(provider)

    result = run_agent(
        "прочитай a.txt",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.answer == "прочитал"
    assert len(provider.sent) == 2

    first, second = provider.sent

    assert first[0]["role"] == "system"

    roles = [message["role"] for message in second]

    assert roles == ["system", "user", "assistant", "tool"]

    assistant = second[2]
    tool = second[3]

    assert assistant["tool_calls"][0]["id"] == "call_1"
    assert tool["tool_call_id"] == "call_1"
    assert "альфа" in tool["content"]
    assert "<<<ДАННЫЕ" in tool["content"]


def test_chat_mode_keeps_pair_after_denial(tmp_path) -> None:
    """Отклонённое действие тоже получает tool-сообщение."""

    (tmp_path / "a.txt").write_text("альфа", encoding="utf-8")

    provider = RecordingProvider(
        [
            _tool_reply(
                "call_9",
                "apply_patch",
                {"path": "a.txt", "old": "альфа", "new": "гамма"},
            ),
            _text_reply("отклонено"),
        ]
    )
    brain = NativeBrain(provider)

    result = run_agent(
        "правь",
        brain,
        tmp_path,
        ground_first=False,
        approve=lambda request: False,
    )

    assert result.answer == "отклонено"

    tool = provider.sent[1][-1]

    assert tool["role"] == "tool"
    assert tool["tool_call_id"] == "call_9"
    assert "отклонил" in tool["content"]

    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "альфа"


def test_chat_mode_finishes_without_tools(tmp_path) -> None:
    """После лимита шагов итог просят без инструментов."""

    provider = RecordingProvider(
        [
            _tool_reply("call_1", "list_dir", {"path": "."}),
            _text_reply("итог по имеющемуся"),
        ]
    )
    brain = NativeBrain(provider)

    result = run_agent(
        "посмотри",
        brain,
        tmp_path,
        max_steps=1,
        ground_first=False,
    )

    assert result.answer == "итог по имеющемуся"
    assert result.error == ""

    # В последнем запросе инструменты не передаются.
    assert provider.payloads[-1].get("tools") is None


def test_chat_is_trimmed_without_orphan_tools() -> None:
    """Сжатие не оставляет tool-сообщение без ассистента."""

    chat = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ]

    for index in range(6):
        chat.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": f"call_{index}"}],
            }
        )
        chat.append(
            {
                "role": "tool",
                "tool_call_id": f"call_{index}",
                "content": "x" * 200,
            }
        )

    trimmed = _trim_chat(chat, 500)

    assert trimmed[0]["role"] == "system"
    assert trimmed[1]["role"] == "user"
    assert trimmed[2]["role"] == "assistant"
    assert all(
        message["role"] != "tool"
        for message in trimmed[:2]
    )
    assert sum(
        len(str(message.get("content") or ""))
        for message in trimmed
    ) < sum(len(str(m.get("content") or "")) for m in chat)


def test_chat_compaction_keeps_recent_and_pairs() -> None:
    """Давние результаты сжимаются, свежие и пары ролей остаются."""

    from terminal.core.agent.loop import _compact_chat

    chat = [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ]

    for index in range(4):
        chat.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": f"call_{index}"}],
            }
        )
        chat.append(
            {
                "role": "tool",
                "tool_call_id": f"call_{index}",
                "content": f"шаг{index}:" + "x" * 2000,
            }
        )

    _compact_chat(chat, recent_steps=2, limit=100)

    assert "старый результат сжат" in chat[3]["content"]
    assert "старый результат сжат" not in chat[-1]["content"]
    assert len(chat[-1]["content"]) > 1000
    assert sum(
        1 for message in chat if message["role"] == "tool"
    ) == 4


def test_smart_excerpt_keeps_error_and_path() -> None:
    """Сжатие не теряет ошибку и путь среди шума."""

    from terminal.core.agent.loop_helpers import _smart_excerpt

    text = "\n".join(
        [f"шум {index} " + "x" * 40 for index in range(40)]
        + [
            "ERROR: terminal/core/agent/loop.py не найден",
            "решение: использовать tools_write.py",
        ]
    )
    result = _smart_excerpt(text, 300)

    assert len(result) <= 300 + 40
    assert "ERROR" in result
    assert "loop.py" in result
    assert "старый результат сжат" in result


def test_salvaged_call_becomes_chat_tool_call(tmp_path) -> None:
    """Вызов, напечатанный текстом, тоже превращается в пару сообщений."""

    (tmp_path / "a.txt").write_text("альфа", encoding="utf-8")

    provider = RecordingProvider(
        [
            _text_reply('read_file({"path": "a.txt"})'),
            _text_reply("готово"),
        ]
    )
    brain = NativeBrain(provider)

    result = run_agent(
        "прочитай a.txt",
        brain,
        tmp_path,
        ground_first=False,
    )

    assert result.answer == "готово"

    assistant = provider.sent[1][2]

    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"][0]["function"]["name"] == "read_file"
