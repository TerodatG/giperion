# Giperion/tests/test_agent_redact.py                                 v001
# Редакция секретов: ключи, пароли, приватные ключи и строки подключения.

import json

from terminal.core.agent.loop import run_agent
from terminal.core.agent.redact import MASK, redact

SECRET = "sk-live-0123456789abcdefghijklmn"


def test_token_with_prefix_is_hidden() -> None:
    """Ключ с узнаваемым префиксом не остаётся в тексте."""

    result = redact(f"ключ: {SECRET}\nконец")

    assert SECRET not in result.text
    assert MASK in result.text
    assert result.hidden == 1


def test_bearer_header_is_hidden() -> None:
    """Токен в заголовке Authorization скрывается."""

    result = redact("Authorization: Bearer abcdef1234567890")

    assert "abcdef1234567890" not in result.text
    assert "Bearer" in result.text


def test_assignment_keeps_name_and_hides_value() -> None:
    """Имя поля остаётся, значение заменяется."""

    result = redact('api_key = "9f8e7d6c5b4a3210"')

    assert "9f8e7d6c5b4a3210" not in result.text
    assert "api_key" in result.text
    assert MASK in result.text


def test_private_key_block_is_hidden() -> None:
    """Приватный ключ скрывается целиком, вместе с телом."""

    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA1234567890abcdef\n"
        "-----END RSA PRIVATE KEY-----"
    )

    result = redact(text)

    assert "MIIEowIBAAKCAQEA" not in result.text
    assert MASK in result.text
    assert result.hidden == 1


def test_url_password_is_hidden() -> None:
    """В строке подключения прячется только пароль."""

    result = redact("postgres://user:supersecret@localhost:5432/db")

    assert "supersecret" not in result.text
    assert "user" in result.text
    assert "localhost" in result.text


def test_references_and_code_are_untouched() -> None:
    """Ссылки на переменные и обычный код не портятся."""

    text = (
        "token = token.strip()\n"
        'api_key = os.environ["AGENT_API_KEY"]\n'
        "self.api_key = value\n"
        "if not token:\n"
        "    return None\n"
    )

    result = redact(text)

    assert result.text == text
    assert result.hidden == 0


def test_placeholder_is_not_hidden() -> None:
    """Заготовки и пустые значения не считаются секретами."""

    text = 'api_key = "your-key-here"\nsecret = ""\ntoken = None\n'

    result = redact(text)

    assert result.text == text
    assert result.hidden == 0


class CapturingBrain:
    """Мозг, который запоминает промпт и сразу отвечает."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def decide(self, prompt: str) -> str:
        self.prompts.append(prompt)

        return json.dumps(
            {"action": "answer", "text": "готово"},
            ensure_ascii=False,
        )


def test_secret_does_not_reach_prompt_or_history(tmp_path) -> None:
    """Прочитанный файл с ключом уходит модели без ключа."""

    (tmp_path / "config.txt").write_text(
        f"api_key = {SECRET}\nplain = значение\n",
        encoding="utf-8",
    )

    brain = CapturingBrain()
    saved: list[list] = []

    result = run_agent(
        "прочитай config.txt",
        brain,
        tmp_path,
        on_history=lambda history: saved.append(list(history)),
    )

    assert SECRET not in brain.prompts[0]
    assert MASK in brain.prompts[0]
    assert SECRET not in saved[0][0][1].text
    assert "plain = значение" in saved[0][0][1].text

    kinds = [step.kind for step in result.steps]
    assert "secret" in kinds

    warning = next(
        step for step in result.steps if step.kind == "secret"
    )
    assert "1" in warning.detail


def test_resume_history_is_cleaned(tmp_path) -> None:
    """Старая история с секретом чистится при продолжении."""

    from terminal.core.agent.protocol import ToolCall, ToolResult

    brain = CapturingBrain()

    run_agent(
        "продолжи",
        brain,
        tmp_path,
        ground_first=False,
        initial_history=[
            (
                ToolCall("read_file", {"path": "config.txt"}),
                ToolResult(True, f"token: {SECRET}"),
            )
        ],
    )

    assert SECRET not in brain.prompts[0]
