# Giperion/tests/test_agent_settings.py                              v001
# Настройки провайдера: файл, окружение, маска ключа.

import pytest

from terminal.core.agent import settings
from terminal.core.agent.providers import provider_from_settings


def test_save_and_load(tmp_path, monkeypatch) -> None:
    """Настройки сохраняются и читаются обратно."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    settings.save_settings(
        "https://api.example.com/v1",
        "secret-key-1234",
        "model-x",
    )

    values = settings.load_settings()

    assert values == {
        "base_url": "https://api.example.com/v1",
        "api_key": "secret-key-1234",
        "model": "model-x",
    }
    assert settings.has_settings(values)


def test_mask_keeps_tail() -> None:
    """Ключ маскируется, последние четыре символа видны."""

    assert settings.mask_key("secret-key-1234").endswith("1234")
    assert "secret" not in settings.mask_key("secret-key-1234")
    assert settings.mask_key("") == ""


def test_file_wins_over_environment(tmp_path, monkeypatch) -> None:
    """Заполненный файл важнее переменных окружения."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )
    monkeypatch.setenv("AGENT_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("AGENT_API_KEY", "env-key")
    monkeypatch.setenv("AGENT_MODEL", "env-model")

    settings.save_settings(
        "https://file.example/v1",
        "file-key",
        "file-model",
    )

    values = settings.resolve_provider_values()

    assert values["base_url"] == "https://file.example/v1"
    assert values["model"] == "file-model"


def test_environment_used_when_file_empty(
    tmp_path,
    monkeypatch,
) -> None:
    """Без файла настройки берутся из окружения."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )
    monkeypatch.setenv("AGENT_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("AGENT_API_KEY", "env-key")
    monkeypatch.setenv("AGENT_MODEL", "env-model")

    values = settings.resolve_provider_values()

    assert values["base_url"] == "https://env.example/v1"
    assert values["api_key"] == "env-key"


def test_provider_is_none_without_settings(
    tmp_path,
    monkeypatch,
) -> None:
    """Без настроек провайдер не создаётся."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )
    monkeypatch.delenv("AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_MODEL", raising=False)

    assert provider_from_settings() is None


def test_provider_is_created_from_file(
    tmp_path,
    monkeypatch,
) -> None:
    """С полными настройками создаётся OpenAI-совместимый провайдер."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )
    settings.save_settings(
        "https://api.example.com/v1",
        "key",
        "model-x",
    )

    provider = provider_from_settings()

    assert provider is not None
    assert provider.model == "model-x"
    assert provider.base_url == "https://api.example.com/v1"


def test_approval_policy_default_and_roundtrip(
    tmp_path,
    monkeypatch,
) -> None:
    """Политика подтверждений по умолчанию confirm и сохраняется."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.approval_policy() == "confirm"

    settings.set_approval_policy("trust")
    assert settings.approval_policy() == "trust"

    settings.set_approval_policy("read")
    assert settings.approval_policy() == "read"

    with pytest.raises(ValueError):
        settings.set_approval_policy("unknown")


def test_plugins_are_off_by_default(tmp_path, monkeypatch) -> None:
    """Плагины включаются только явно и сохраняются в файле."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.plugins_enabled() is False

    settings.set_plugins_enabled(True)
    assert settings.plugins_enabled() is True

    settings.set_plugins_enabled(False)
    assert settings.plugins_enabled() is False


def test_stream_and_timeout_settings(tmp_path, monkeypatch) -> None:
    """Поток и таймаут сохраняются и читаются."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.stream_enabled() is False
    assert settings.request_timeout() == settings.DEFAULT_TIMEOUT

    settings.set_stream_enabled(True)
    settings.set_request_timeout(45)

    assert settings.stream_enabled() is True
    assert settings.request_timeout() == 45

    # Выход за границы подрезается, мусор не ломает чтение.
    settings.set_request_timeout(5000)
    assert settings.request_timeout() == 900

    (tmp_path / "agent_settings.json").write_text(
        '{"request_timeout": "долго"}',
        encoding="utf-8",
    )

    assert settings.request_timeout() == settings.DEFAULT_TIMEOUT


def test_task_controls_settings(tmp_path, monkeypatch) -> None:
    """Шаги и выбранная модель сохраняются и подрезаются."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.max_steps() == 12
    assert settings.model_choice() == ""

    settings.set_max_steps(20)
    settings.set_model_choice("go-qwen3.8-flash")

    assert settings.max_steps() == 20
    assert settings.model_choice() == "go-qwen3.8-flash"

    settings.set_max_steps(0)
    assert settings.max_steps() == 1

    settings.set_max_steps(1000)
    assert settings.max_steps() == 40

    settings.set_model_choice("")
    assert settings.model_choice() == ""

def test_step_timeout_setting(tmp_path, monkeypatch) -> None:
    """Таймаут шага сохраняется и подрезается."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.step_timeout() == 180

    settings.set_step_timeout(300)
    assert settings.step_timeout() == 300

    settings.set_step_timeout(0)
    assert settings.step_timeout() == 0

    settings.set_step_timeout(9999)
    assert settings.step_timeout() == 3600

def test_context_auto_setting(tmp_path, monkeypatch) -> None:
    """Автобюджет включён по умолчанию и сохраняется."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.context_auto() is True

    settings.set_context_auto(False)
    assert settings.context_auto() is False

    settings.set_context_auto(True)
    assert settings.context_auto() is True


def test_project_policy_overrides_global(tmp_path, monkeypatch) -> None:
    """Политика проекта хранится отдельно и важнее глобальной."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )
    monkeypatch.setattr(
        settings,
        "PROJECT_POLICIES_FILE",
        tmp_path / "agent_policies.json",
    )
    root = tmp_path / "project"
    root.mkdir()
    settings.set_approval_policy("confirm")

    assert not settings.has_project_policy(root)
    assert settings.project_policy(root) == "confirm"

    settings.set_project_policy(root, "trust")

    assert settings.has_project_policy(root)
    assert settings.project_policy(root) == "trust"

    with pytest.raises(ValueError):
        settings.set_project_policy(root, "unknown")
