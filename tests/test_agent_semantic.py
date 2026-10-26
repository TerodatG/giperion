# Giperion/tests/test_agent_semantic.py                                v001
# Смысловой поиск: слова, чанки, BM25, гибрид с эмбеддингами и кеш.

import pytest

from terminal.core.agent import embeddings, semantic, settings
from terminal.core.agent.protocol import ToolCall


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Кеши в памяти и файлы — в tmp_path."""

    semantic.reset_cache()
    monkeypatch.setattr(semantic, "CACHE_FILE", tmp_path / "semantic.json")
    monkeypatch.setattr(semantic, "VECTOR_FILE", tmp_path / "vectors.json")
    monkeypatch.setattr(
        semantic.embeddings,
        "client",
        lambda: None,
    )

    yield

    semantic.reset_cache()


def _project(tmp_path, files: dict[str, str]):
    """Создаёт файлы проекта и возвращает корень."""

    root = tmp_path / "project"

    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    return root


def test_tokens_split_names() -> None:
    """camelCase и snake_case делятся, стоп-слова выбрасываются."""

    assert semantic.tokens("findRelevant") == ["find", "relevant"]
    assert semantic.tokens("find_relevant путь") == [
        "find",
        "relevant",
        "путь",
    ]
    assert semantic.tokens("и в на the a почему") == []
    assert semantic.tokens("AppContainer") == ["app", "container"]


def test_stem_matches_cases() -> None:
    """Падежи и числа сводятся к одной основе."""

    assert semantic.stem("подтверждения") == semantic.stem("подтверждение")
    assert semantic.stem("файлов") == semantic.stem("файлы") == "файл"
    assert semantic.stem("записи") == semantic.stem("запись")
    assert semantic.stem("путь") == "путь"
    assert semantic.stem("tests") == "test"
    assert semantic.stem("class") == "class"


def test_chunks_for_python_and_markdown(tmp_path) -> None:
    """Функции и разделы становятся отдельными фрагментами."""

    root = _project(
        tmp_path,
        {
            "a.py": "def alpha():\n    return 1\n",
            "docs/guide.md": "# Гид\n\n## Настройка\nтекст\n",
        },
    )

    found = semantic.load_chunks(root)["chunks"]
    pairs = {(item["path"], item["name"], item["kind"]) for item in found}

    assert ("a.py", "alpha", "function") in pairs
    assert ("docs/guide.md", "Настройка", "section") in pairs


def test_module_docstring_is_indexed(tmp_path) -> None:
    """Docstring модуля попадает в индекс отдельным фрагментом."""

    root = _project(
        tmp_path,
        {"m.py": '"""Смысловой поиск и эмбеддинги."""\n\n\ndef run():\n    return 1\n'},
    )

    found = semantic.load_chunks(root)["chunks"]
    modules = [
        item for item in found if item["kind"] == "module"
    ]

    assert modules
    assert modules[0]["name"] == "m.py"
    assert "Смысловой поиск" in modules[0]["text"]


def test_code_beats_tests(tmp_path) -> None:
    """При равном совпадении код проекта выше тестов."""

    body = 'def probe():\n    return "уникальный маркер"\n'
    root = _project(
        tmp_path,
        {
            "tests/test_probe.py": body,
            "terminal/core/probe.py": body,
        },
    )

    result = semantic.find_relevant(root, "уникальный маркер")
    first = result.text.splitlines()[1]

    assert "terminal/core/probe.py" in first


def test_lexical_ranking(tmp_path) -> None:
    """BM25 ставит наверх файл про нужную тему."""

    root = _project(
        tmp_path,
        {
            "docs/plugins.md": (
                "# Плагины\nИзоляция плагинов в отдельном процессе "
                "и AppContainer.\n"
            ),
            "docs/tests.md": (
                "# Тесты\nЗапуск pytest и проверка структуры проекта.\n"
            ),
        },
    )

    result = semantic.find_relevant(root, "изоляция плагинов")

    assert result.ok
    first = result.text.splitlines()[1]

    assert "docs/plugins.md" in first
    assert "только слова" in result.text


def test_cache_rebuilds_after_change(tmp_path) -> None:
    """Новый файл виден без перезапуска и ручного сброса."""

    root = _project(tmp_path, {"a.py": "def alpha():\n    return 1\n"})

    semantic.find_relevant(root, "alpha")

    (root / "b.py").write_text(
        "def quantum_flux():\n    return 2\n",
        encoding="utf-8",
    )

    result = semantic.find_relevant(root, "quantum flux")

    assert "b.py" in result.text


def test_hybrid_uses_embeddings(tmp_path, monkeypatch) -> None:
    """Без общих слов наверх выходит фрагмент, близкий по вектору."""

    root = _project(
        tmp_path,
        {
            "meaning.py": "def store_vectors():\n    return 'семантика'\n",
            "other.py": "def launch_tests():\n    return 'pytest'\n",
        },
    )

    monkeypatch.setattr(
        embeddings,
        "client",
        lambda: ("http://127.0.0.1:1234/v1", "", "fake-embed"),
    )

    def fake_embed(texts, *, target=None, timeout=30):
        return [
            [1.0, 0.0]
            if ("семантика" in text or "смысловая" in text)
            else [0.0, 1.0]
            for text in texts
        ]

    monkeypatch.setattr(embeddings, "embed", fake_embed)

    result = semantic.find_relevant(root, "смысловая близость")

    assert result.ok
    assert "meaning.py" in result.text.splitlines()[1]
    assert "эмбеддинги «fake-embed»" in result.text


def test_hybrid_falls_back_on_error(tmp_path, monkeypatch) -> None:
    """Ошибка эмбеддингов не ломает поиск: остаются слова."""

    root = _project(
        tmp_path,
        {"plugins.md": "# Плагины\nИзоляция плагинов.\n"},
    )

    monkeypatch.setattr(
        embeddings,
        "client",
        lambda: ("http://127.0.0.1:1234/v1", "", "fake"),
    )

    def broken(*args, **kwargs):
        raise embeddings.EmbeddingError("нет связи")

    monkeypatch.setattr(embeddings, "embed", broken)

    result = semantic.find_relevant(root, "плагины")

    assert result.ok
    assert "plugins.md" in result.text
    assert "эмбеддинги недоступны" in result.text


def test_empty_query_is_rejected(tmp_path) -> None:
    """Запрос из одних стоп-слов не ищется."""

    root = _project(tmp_path, {"a.py": "def alpha():\n    return 1\n"})

    assert not semantic.find_relevant(root, "и в на").ok
    assert not semantic.find_relevant(root, "").ok


def test_tool_is_registered_as_read(tmp_path, monkeypatch) -> None:
    """find_relevant — читающий инструмент с проверкой аргументов."""

    from terminal.core.agent import registry

    spec = registry.get_spec("find_relevant")

    assert spec is not None
    assert spec.risk == "read"
    assert spec.required == ("query",)

    invalid = registry.execute(
        tmp_path,
        ToolCall("find_relevant", {}),
    )

    assert not invalid.ok

    root = _project(tmp_path, {"a.py": "def alpha():\n    return 1\n"})
    result = registry.execute(
        root,
        ToolCall("find_relevant", {"query": "alpha", "limit": 3}),
    )

    assert result.ok
    assert "a.py" in result.text


def test_semantic_settings_defaults(tmp_path, monkeypatch) -> None:
    """Поиск включён, модель эмбеддингов определяется сама."""

    monkeypatch.setattr(
        settings,
        "SETTINGS_FILE",
        tmp_path / "agent_settings.json",
    )

    assert settings.semantic_enabled() is True
    assert settings.embedding_model() == ""

    settings.set_semantic_enabled(False)
    settings.set_embedding_model("my-embed")

    assert settings.semantic_enabled() is False
    assert settings.embedding_model() == "my-embed"

def test_vector_only_hit(tmp_path, monkeypatch) -> None:
    """Фрагмент без общих слов находится по вектору, а не по BM25."""

    root = _project(
        tmp_path,
        {
            "a.py": "def alpha():\n    return 'общий термин'\n",
            "b.py": "def beta():\n    return 'смысл'\n",
        },
    )

    monkeypatch.setattr(semantic, "CANDIDATES", 1)
    monkeypatch.setattr(
        embeddings,
        "client",
        lambda: ("http://127.0.0.1:1234/v1", "", "fake-embed"),
    )

    def fake_embed(texts, *, target=None, timeout=30):
        return [
            [1.0, 0.0]
            if ("смысл" in text or text.strip() == "общий термин")
            else [0.0, 1.0]
            for text in texts
        ]

    monkeypatch.setattr(embeddings, "embed", fake_embed)

    chunks = semantic.load_chunks(root)["chunks"]
    added, total = semantic.cache_vectors(chunks, batch=2)

    assert added == total == len(chunks)

    result = semantic.find_relevant(root, "общий термин")
    first = result.text.splitlines()[1]

    assert "b.py" in first
    assert "2/2 фрагментов" in result.text


def test_cache_vectors_is_incremental(tmp_path, monkeypatch) -> None:
    """Векторы считаются пачками и не пересчитываются повторно."""

    root = _project(
        tmp_path,
        {
            "a.py": "def alpha():\n    return 1\n",
            "b.py": "def beta():\n    return 2\n",
            "c.py": "def gamma():\n    return 3\n",
        },
    )

    batches: list[int] = []

    monkeypatch.setattr(
        embeddings,
        "client",
        lambda: ("http://127.0.0.1:1234/v1", "", "fake-embed"),
    )

    def fake_embed(texts, *, target=None, timeout=30):
        batches.append(len(texts))

        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(embeddings, "embed", fake_embed)

    chunks = semantic.load_chunks(root)["chunks"]

    added, total = semantic.cache_vectors(chunks, batch=2)

    assert added == total == len(chunks)
    assert batches == [2, 1]

    again, again_total = semantic.cache_vectors(chunks, batch=2)

    assert again == 0
    assert again_total == 0


def test_vector_stats(tmp_path, monkeypatch) -> None:
    """Покрытие показывает модель и число фрагментов с вектором."""

    root = _project(
        tmp_path,
        {"a.py": "def alpha():\n    return 1\n"},
    )

    monkeypatch.setattr(embeddings, "client", lambda: None)

    stats = semantic.vector_stats(root)

    assert stats["model"] == ""
    assert stats["covered"] == 0
    assert stats["total"] >= 1

    monkeypatch.setattr(
        embeddings,
        "client",
        lambda: ("http://127.0.0.1:1234/v1", "", "fake-embed"),
    )
    monkeypatch.setattr(
        embeddings,
        "embed",
        lambda texts, *, target=None, timeout=30: [
            [1.0, 0.0] for _ in texts
        ],
    )

    chunks = semantic.load_chunks(root)["chunks"]
    semantic.cache_vectors(chunks, batch=8)

    stats = semantic.vector_stats(root)

    assert stats["model"] == "fake-embed"
    assert stats["covered"] == stats["total"]


def test_cache_vectors_needs_local_provider(tmp_path, monkeypatch) -> None:
    """Без локального провайдера глубокий индекс не строится."""

    root = _project(
        tmp_path,
        {"a.py": "def alpha():\n    return 1\n"},
    )

    monkeypatch.setattr(embeddings, "client", lambda: None)

    chunks = semantic.load_chunks(root)["chunks"]

    with pytest.raises(embeddings.EmbeddingError):
        semantic.cache_vectors(chunks)

