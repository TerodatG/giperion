# Giperion/tests/test_browser_scenario.py                               v001
# Браузерный сценарий: чтение JSON и повтор действий.

import json

from terminal.core.agent.protocol import ToolResult
from tools import browser_scenario


def test_load_and_run(monkeypatch, tmp_path) -> None:
    """Сценарий передаёт URL и действия в browser_js.act."""

    scenario = tmp_path / "scenario.json"
    scenario.write_text(
        json.dumps(
            {
                "url": "https://example.com/login",
                "actions": [{"type": "fill", "selector": "#user", "text": "u"}],
                "wait": "#form",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    calls = {}

    def fake_act(root, url, **kwargs):
        calls.update(root=root, url=url, **kwargs)

        return ToolResult(True, "готово")

    monkeypatch.setattr(browser_scenario.browser_js, "act", fake_act)

    result = browser_scenario.run(scenario, tmp_path)

    assert result["ok"]
    assert result["text"] == "готово"
    assert calls["url"] == "https://example.com/login"
    assert calls["wait"] == "#form"
    assert calls["actions"][0]["selector"] == "#user"


def test_bad_scenario(tmp_path) -> None:
    """Без url сценарий отклоняется."""

    scenario = tmp_path / "bad.json"
    scenario.write_text("{}", encoding="utf-8")

    try:
        browser_scenario.load(scenario)
    except ValueError as error:
        assert "url" in str(error)
    else:
        raise AssertionError("ожидалась ошибка")
