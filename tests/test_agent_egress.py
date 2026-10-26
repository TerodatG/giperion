# Giperion/tests/test_agent_egress.py                                  v001
# Общий allowlist доменов для веба, браузера и MCP.

import pytest

from terminal.core.agent import browser_js, mcp_policy, settings, web


@pytest.fixture(autouse=True)
def _settings(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )


def test_egress_defaults_to_all() -> None:
    """Пустой allowlist разрешает любой публичный домен."""

    assert settings.egress_domains() == ()
    assert web.egress_allowed("example.com")


def test_egress_patterns() -> None:
    """Точный домен и *.поддомены работают."""

    settings.set_egress_domains(["example.com", "*.wikipedia.org"])

    assert web.egress_allowed("example.com")
    assert web.egress_allowed("ru.wikipedia.org")
    assert not web.egress_allowed("wikipedia.org")
    assert not web.egress_allowed("python.org")


def test_browser_respects_egress(monkeypatch) -> None:
    """Браузер не идёт на домен вне общего allowlist."""

    monkeypatch.setattr(
        web,
        "validate_url",
        lambda url: "https://python.org/",
    )
    monkeypatch.setattr(web, "host_of", lambda url: "python.org")
    monkeypatch.setattr(web, "is_public_host", lambda host: True)
    monkeypatch.setattr(
        web,
        "egress_allowed",
        lambda host: host == "example.com",
    )

    with pytest.raises(web.WebError):
        browser_js._check("https://python.org/")


def test_mcp_respects_egress(monkeypatch) -> None:
    """MCP-инструмент не ходит на домен вне общего allowlist."""

    monkeypatch.setattr(
        settings,
        "egress_domains",
        lambda: ("example.com",),
    )

    server = mcp_policy.McpServer("web", "python")

    assert mcp_policy.check_domains(
        server,
        {"url": "https://example.com/x"},
    ) == ""
    assert "общий allowlist" in mcp_policy.check_domains(
        server,
        {"url": "https://python.org/"},
    )
