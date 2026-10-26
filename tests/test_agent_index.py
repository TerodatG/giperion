# Giperion/tests/test_agent_index.py                                   v001
# Индекс проекта, чтение по строкам и бюджет контекста.

import json

from terminal.core.agent import index, registry, tools
from terminal.core.agent.protocol import ToolCall

SOURCE = '''class Greeter:
    """Простое приветствие."""

    def greet(self, name):
        return "привет, " + name

    class Inner:
        def deep(self):
            return 1


def build_greeter():
    return Greeter()


async def fetch_name():
    return "имя"
'''


def _project(tmp_path):
    (tmp_path / "greet.py").write_text(SOURCE, encoding="utf-8")
    (tmp_path / "other.py").write_text(
        "def greet_other():\n    return 2\n",
        encoding="utf-8",
    )

    return tmp_path


def test_index_finds_classes_and_methods(tmp_path, monkeypatch) -> None:
    """Индекс видит классы, методы, вложенные классы и функции."""

    monkeypatch.setattr(index, "INDEX_FILE", tmp_path / "index.json")
    project = _project(tmp_path)

    document = index.build_index(project)
    names = {item["name"]: item for item in document["symbols"]}

    assert names["Greeter"]["kind"] == "class"
    assert names["Greeter.greet"]["kind"] == "method"
    assert names["Greeter.Inner.deep"]["kind"] == "method"
    assert names["build_greeter"]["kind"] == "function"
    assert names["fetch_name"]["kind"] == "function"
    assert names["Greeter"]["path"] == "greet.py"

    assert names["Greeter"]["line"] < names["Greeter.greet"]["line"]


def test_find_symbol_ranks_exact_match_first(tmp_path, monkeypatch) -> None:
    """Точное совпадение идёт раньше частичного."""

    monkeypatch.setattr(index, "INDEX_FILE", tmp_path / "index.json")
    project = _project(tmp_path)

    result = index.find_symbol(project, "greet")

    assert result.ok
    first = result.text.splitlines()[1]

    assert "Greeter.greet" in first


def test_find_symbol_reports_missing(tmp_path, monkeypatch) -> None:
    """Если символ не найден, предлагается search_text."""

    monkeypatch.setattr(index, "INDEX_FILE", tmp_path / "index.json")
    project = _project(tmp_path)

    result = index.find_symbol(project, "нетакого")

    assert result.ok
    assert "не найден" in result.text


def test_index_cache_is_reused(tmp_path, monkeypatch) -> None:
    """Свежий индекс не перестраивается без нужды."""

    cache = tmp_path / "index.json"
    monkeypatch.setattr(index, "INDEX_FILE", cache)
    project = _project(tmp_path)

    index.build_index(project)
    stamp = cache.stat().st_mtime_ns

    document = index.load_index(project)

    assert document["symbols"]
    assert cache.stat().st_mtime_ns == stamp


def test_read_file_range(tmp_path) -> None:
    """Чтение части файла возвращает нужные строки и заголовок."""

    target = tmp_path / "a.txt"
    target.write_text("1\n2\n3\n4\n5\n", encoding="utf-8")

    result = tools.read_file(tmp_path, "a.txt", start=2, limit=2)

    assert result.ok
    assert "строки 2–3 из 5" in result.text
    assert "2\n3" in result.text
    assert "1\n" not in result.text.split("\n\n", 1)[-1]

    beyond = tools.read_file(tmp_path, "a.txt", start=10)

    assert not beyond.ok
    assert "вне файла" in beyond.text


def test_registry_exposes_symbol_tool(tmp_path, monkeypatch) -> None:
    """Инструмент find_symbol доступен модели и работает через реестр."""

    monkeypatch.setattr(index, "INDEX_FILE", tmp_path / "index.json")
    project = _project(tmp_path)

    schema = next(
        item
        for item in registry.tool_schemas()
        if item["function"]["name"] == "find_symbol"
    )

    assert schema["function"]["parameters"]["required"] == ["query"]

    result = registry.execute(
        project,
        ToolCall("find_symbol", {"query": "build_greeter"}),
    )

    assert result.ok
    assert "greet.py" in result.text

    read_schema = next(
        item
        for item in registry.tool_schemas()
        if item["function"]["name"] == "read_file"
    )
    properties = read_schema["function"]["parameters"]["properties"]

    assert properties["start"]["type"] == "integer"
    assert properties["limit"]["type"] == "integer"


def test_load_index_uses_memory_cache(tmp_path, monkeypatch) -> None:
    """Повторный поиск не читает 300 КБ JSON с диска."""

    cache = tmp_path / "index.json"
    monkeypatch.setattr(index, "INDEX_FILE", cache)
    project = _project(tmp_path)

    first = index.load_index(project)

    def broken(*args, **kwargs):
        raise AssertionError("файл индекса прочитан повторно")

    monkeypatch.setattr(index, "read_json_object", broken)

    second = index.load_index(project)

    assert second is first
    assert second["symbols"]


def test_context_budget_setting(tmp_path, monkeypatch) -> None:
    """Бюджет контекста сохраняется и подрезается по границам."""

    from terminal.core.agent import settings

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.context_limit_chars() == 60_000

    settings.set_context_limit_chars(90_000)
    assert settings.context_limit_chars() == 90_000

    settings.set_context_limit_chars(100)
    assert settings.context_limit_chars() == 8_000

    settings.set_context_limit_chars(10_000_000)
    assert settings.context_limit_chars() == 2_000_000

    (tmp_path / "agent_settings.json").write_text(
        json.dumps({"context_chars": "много"}),
        encoding="utf-8",
    )

    assert settings.context_limit_chars() == 60_000

def test_docs_headings_are_indexed(tmp_path, monkeypatch) -> None:
    """Заголовки markdown находятся через find_symbol."""

    monkeypatch.setattr(index, "INDEX_FILE", tmp_path / "index.json")
    (tmp_path / "README.md").write_text(
        "# Установка\nтекст\n## Настройка провайдера\n",
        encoding="utf-8",
    )

    result = index.find_symbol(tmp_path, "Настройка")

    assert result.ok
    assert "README.md" in result.text
    assert "section" in result.text


def test_index_rebuilds_after_change(tmp_path, monkeypatch) -> None:
    """После правки файла индекс перестраивается без ожидания TTL."""

    monkeypatch.setattr(index, "INDEX_FILE", tmp_path / "index.json")
    target = tmp_path / "a.py"
    target.write_text("def first():\n    return 1\n", encoding="utf-8")

    index.build_index(tmp_path)

    target.write_text("def second():\n    return 2\n", encoding="utf-8")

    result = index.find_symbol(tmp_path, "second")

    assert result.ok
    assert "a.py" in result.text
