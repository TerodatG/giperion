# Giperion/tests/test_agent_embeddings.py                              v001
# Клиент эмбеддингов: локальность, автопоиск модели, векторы и косинус.

import pytest

from terminal.core.agent import embeddings


def test_local_urls_only() -> None:
    """Эмбеддинги разрешены только для этой машины."""

    assert embeddings.is_local_url("http://127.0.0.1:1234/v1")
    assert embeddings.is_local_url("http://localhost:1234/v1")
    assert embeddings.is_local_url("http://[::1]:1234/v1")
    assert not embeddings.is_local_url("https://api.example.com/v1")
    assert not embeddings.is_local_url("")
    assert not embeddings.is_local_url("не url")


def test_detect_model_picks_embedding(monkeypatch) -> None:
    """Из /models выбирается модель со словом embed."""

    calls: list[str] = []

    def fake(url: str, api_key: str, payload) -> dict:
        calls.append(url)

        return {
            "data": [
                {"id": "qwen3-coder-30b"},
                {"id": "text-embedding-nomic-embed-text-v1.5"},
            ]
        }

    embeddings._detected.clear()
    monkeypatch.setattr(embeddings, "_json_request", fake)

    model = embeddings.detect_model(
        "http://127.0.0.1:1234/v1",
        "key",
    )

    assert model == "text-embedding-nomic-embed-text-v1.5"
    assert calls == ["http://127.0.0.1:1234/v1/models"]


def test_client_needs_local_provider(monkeypatch) -> None:
    """Удалённый провайдер и выключенный поиск дают None."""

    monkeypatch.setattr(
        embeddings.settings,
        "semantic_enabled",
        lambda: True,
    )

    monkeypatch.setattr(
        embeddings,
        "_provider_values",
        lambda: {"base_url": "https://api.example.com/v1", "api_key": "k"},
    )

    assert embeddings.client() is None

    monkeypatch.setattr(
        embeddings,
        "_provider_values",
        lambda: {"base_url": "http://127.0.0.1:1234/v1", "api_key": ""},
    )
    monkeypatch.setattr(
        embeddings.settings,
        "embedding_model",
        lambda: "text-embedding-nomic-embed-text-v1.5",
    )

    assert embeddings.client() == (
        "http://127.0.0.1:1234/v1",
        "",
        "text-embedding-nomic-embed-text-v1.5",
    )

    monkeypatch.setattr(
        embeddings.settings,
        "semantic_enabled",
        lambda: False,
    )

    assert embeddings.client() is None


def test_embed_sends_batch(monkeypatch) -> None:
    """Батч уходит на /embeddings с моделью и возвращает векторы."""

    captured: dict = {}

    target = ("http://127.0.0.1:1234/v1", "key", "embed-model")

    def fake(url: str, api_key: str, payload: dict) -> dict:
        captured["url"] = url
        captured["payload"] = payload

        return {
            "data": [
                {"embedding": [1, 0.5]},
                {"embedding": [0, 1]},
            ]
        }

    monkeypatch.setattr(embeddings, "_json_request", fake)

    vectors = embeddings.embed(["первый", "второй"], target=target)

    assert captured["url"].endswith("/embeddings")
    assert captured["payload"] == {
        "model": "embed-model",
        "input": ["первый", "второй"],
    }
    assert vectors == [[1.0, 0.5], [0.0, 1.0]]


def test_embed_rejects_broken_response(monkeypatch) -> None:
    """Неверное число векторов — ошибка, а не тихий пропуск."""

    monkeypatch.setattr(
        embeddings,
        "_json_request",
        lambda *args: {"data": [{"embedding": [1.0]}]},
    )

    with pytest.raises(embeddings.EmbeddingError):
        embeddings.embed(
            ["а", "б"],
            target=("http://127.0.0.1:1234/v1", "", "m"),
        )


def test_embed_without_client(monkeypatch) -> None:
    """Без настроенного клиента вызов падает понятной ошибкой."""

    monkeypatch.setattr(embeddings, "client", lambda: None)

    with pytest.raises(embeddings.EmbeddingError):
        embeddings.embed(["текст"])

    assert embeddings.embed([]) == []


def test_cosine() -> None:
    """Косинус считает близость и не делится на ноль."""

    assert embeddings.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert embeddings.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert embeddings.cosine([], [1.0]) == 0.0
    assert embeddings.cosine([0, 0], [1, 1]) == 0.0
