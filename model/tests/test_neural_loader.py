# GiperionModel/tests/test_neural_loader.py                            v002
# Загрузчик нейросети: ответы, кеш и защита от гонки.

import json
import threading
import time

from giperion_model import neural_engine, neural_loader


def test_intent_responses_are_loaded() -> None:
    """Загрузчик собирает ответы по тегам намерений."""

    responses = neural_loader.load_responses()

    assert "greeting" in responses
    assert responses["greeting"]


def test_intent_responses_accept_list_document(
    tmp_path,
    monkeypatch,
) -> None:
    """Список intents.json поддерживается так же, как объект."""

    path = tmp_path / "intents.json"
    path.write_text(
        json.dumps(
            [
                {
                    "tag": "greeting",
                    "patterns": ["привет"],
                    "responses": ["здравствуй"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(neural_loader, "INTENTS_FILE", path)

    assert neural_loader.load_responses() == {
        "greeting": ["здравствуй"]
    }


def test_reload_engine_resets_cache(monkeypatch) -> None:
    """После сброса следующее обращение загружает модели заново."""

    monkeypatch.setattr(neural_engine, "_engine", object())
    monkeypatch.setattr(neural_engine, "_engine_checked", True)

    neural_engine.reload_engine()

    assert neural_engine._engine is None
    assert neural_engine._engine_checked is False


def test_engine_is_built_once_under_concurrency(monkeypatch) -> None:
    """Параллельные запросы не должны строить движок много раз."""

    builds: list[int] = []

    class FakeEngine:
        def reply_with_confidence(self, message):
            return None

    def fake_build():
        builds.append(1)
        time.sleep(0.03)

        return FakeEngine()

    monkeypatch.setattr(neural_engine, "_engine", None)
    monkeypatch.setattr(neural_engine, "_engine_checked", False)
    monkeypatch.setattr(neural_engine, "_build_engine", fake_build)

    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait()
        neural_engine.get_neural_reply("тест")

    threads = [
        threading.Thread(target=worker)
        for _ in range(8)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert len(builds) == 1


def test_router_works_without_generator(monkeypatch) -> None:
    """Без seq2seq движок собирается вокруг роутера."""

    fake_router = object()

    monkeypatch.setattr(
        neural_loader.LinearIntentRouter,
        "load",
        staticmethod(lambda: fake_router),
    )
    monkeypatch.setattr(
        neural_loader,
        "load_generator",
        lambda device, tokenizer: (None, {}),
    )
    monkeypatch.setattr(
        neural_loader,
        "load_responses",
        lambda: {"greeting": ["привет"]},
    )

    parts = neural_loader.load_components()

    assert parts is not None
    assert parts["router"] is fake_router
    assert parts["generator"] is None
    assert parts["responses_by_tag"] == {"greeting": ["привет"]}
    assert "classifier" not in parts


def test_router_is_the_only_classifier() -> None:
    """В рантайме нет CNN: классификатор — только роутер."""

    parts = neural_loader.load_components()

    assert parts is not None
    assert parts["router"] is not None
    assert "classifier" not in parts
