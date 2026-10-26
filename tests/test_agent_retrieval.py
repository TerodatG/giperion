# Giperion/tests/test_agent_retrieval.py                               v001
# Retrieval-бенчмарк смыслового поиска: ожидаемый файл в топ-5.

import pytest

from config import BASE_DIR
from terminal.core.agent import embeddings, semantic
from tools.retrieval_cases import CASES


@pytest.fixture(autouse=True)
def _bm25_only(monkeypatch):
    """Бенчмарк не зависит от запущенного сервера эмбеддингов."""

    monkeypatch.setattr(embeddings, "client", lambda: None)


def _paths(text: str) -> list[str]:
    return [
        line[2:].split(":", 1)[0].strip()
        for line in str(text or "").splitlines()
        if line.startswith("- ")
    ]


def test_retrieval_cases_hit_at_five() -> None:
    """Каждый запрос находит свой файл в первых пяти фрагментах."""

    failures = []

    for query, expected in CASES:
        result = semantic.find_relevant(BASE_DIR, query, limit=5)
        paths = _paths(result.text)

        if expected not in paths:
            failures.append((query, expected, paths))

    assert not failures, failures
