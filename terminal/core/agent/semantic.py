# Giperion/terminal/core/agent/semantic.py                             v002
# Смысловой поиск: BM25 по фрагментам и переранжирование эмбеддингами.
# Последнее изменение: фрагменты и токены вынесены в semantic_index/text.

from collections import Counter
from pathlib import Path

from config import DATA_DIR
from shared.storage.json_store import read_json_object, write_json
from terminal.core.agent import embeddings, semantic_index
from terminal.core.agent.protocol import ToolResult
from terminal.core.agent.semantic_text import (
    index_tokens,
    stem,  # noqa: F401 — реэкспорт для тестов
    tokens,
)

CACHE_FILE = DATA_DIR / "agent_semantic.json"
VECTOR_FILE = DATA_DIR / "agent_vectors.json"
CANDIDATES = 80
MAX_EMBED_PER_CALL = 120
MAX_VECTORS = 4000
DEFAULT_LIMIT = 8
SNIPPET = 200
K1 = 1.5
B = 0.75
VECTOR_WEIGHT = 0.65
LEXICAL_WEIGHT = 0.35
PATH_WEIGHTS = (("tests/", 0.7), ("docs/", 0.92))

_STATS: dict[str, tuple] = {}
_VECTORS: dict[tuple[str, str], dict[str, list[float]]] = {}


def reset_cache() -> None:
    """Забывает кеши в памяти (нужно тестам и переключению проектов)."""

    _STATS.clear()
    _VECTORS.clear()
    semantic_index.reset_cache()


def load_chunks(root: Path, refresh: bool = False) -> dict:
    """Фрагменты проекта по текущим путям кеша."""

    return semantic_index.load(
        root,
        CACHE_FILE,
        (CACHE_FILE, VECTOR_FILE),
        refresh=refresh,
    )


def _signature(chunks: list[dict]) -> str:
    """Отпечаток набора фрагментов (совместимость и fallback)."""

    return semantic_index.signature(chunks)


def _counters(chunks: list[dict], signature: str) -> tuple:
    """Счётчики слов, длины и средняя длина для BM25."""

    cached = _STATS.get(signature)

    if cached is not None:
        return cached

    counts = []
    lengths = []

    for chunk in chunks:
        words = index_tokens(
            chunk.get("payload") or chunk.get("text") or ""
        )
        counter = Counter(words)
        counts.append(counter)
        lengths.append(max(1, len(words)))

    average = sum(lengths) / max(1, len(lengths))
    value = (counts, lengths, average)
    _STATS.clear()
    _STATS[signature] = value

    return value


def _lexical(chunks: list[dict], signature: str, query: str) -> list[float]:
    """Оценка BM25 по словам запроса."""

    counts, lengths, average = _counters(chunks, signature)
    words = index_tokens(query)

    if not words:
        return [0.0] * len(chunks)

    total = len(chunks)
    scores = [0.0] * total

    for word in dict.fromkeys(words):
        containing = sum(1 for counter in counts if word in counter)

        if not containing:
            continue

        inverse = (total - containing + 0.5) / (containing + 0.5)

        for index, counter in enumerate(counts):
            frequency = counter.get(word, 0)

            if not frequency:
                continue

            norm = 1 - B + B * lengths[index] / average
            scores[index] += (
                inverse
                * frequency
                * (K1 + 1)
                / (frequency + K1 * norm)
            )

    return scores


def _load_vectors(model: str) -> dict[str, list[float]]:
    """Векторы из кеша для текущей модели."""

    key = ("file", model)
    cached = _VECTORS.get(key)

    if cached is not None:
        return cached

    document = read_json_object(VECTOR_FILE)
    stored: dict[str, list[float]] = {}

    if str(document.get("model")) == model:
        raw = document.get("vectors")

        if isinstance(raw, dict):
            for name, vector in raw.items():
                if isinstance(vector, list) and vector:
                    stored[str(name)] = [float(item) for item in vector]

    _VECTORS[key] = stored

    return stored


def _save_vectors(model: str, stored: dict[str, list[float]]) -> None:
    """Сохраняет векторы, обрезая самые старые записи."""

    if len(stored) > MAX_VECTORS:
        keep = list(stored.items())[-MAX_VECTORS:]
        stored.clear()
        stored.update(keep)

    try:
        write_json(
            VECTOR_FILE,
            {"model": model, "vectors": stored},
        )
    except OSError:
        pass


def _embed_missing(
    target: tuple[str, str, str],
    chunks: list[dict],
) -> tuple[dict[str, list[float]], str]:
    """Векторы кандидатов; добирает отсутствующие у сервера."""

    model = target[2]
    stored = _load_vectors(model)
    missing = [
        chunk
        for chunk in chunks
        if chunk["hash"] not in stored
    ][:MAX_EMBED_PER_CALL]

    if not missing:
        return stored, ""

    try:
        vectors = embeddings.embed(
            [chunk["payload"] for chunk in missing],
            target=target,
            timeout=60,
        )
    except embeddings.EmbeddingError as error:
        return stored, str(error)

    for chunk, vector in zip(missing, vectors):
        stored[chunk["hash"]] = [
            round(float(value), 4) for value in vector
        ]

    _save_vectors(model, stored)

    return stored, ""


def _hybrid(
    ranked: list[int],
    chunks: list[dict],
    lexical: list[float],
    query: str,
) -> tuple[dict[int, float], str]:
    """Пересчёт кандидатов по косинусу; пусто — эмбеддинги недоступны."""

    target = embeddings.client()

    if target is None:
        return {}, ""

    try:
        query_vector = embeddings.embed(
            [query],
            target=target,
            timeout=30,
        )[0]
    except Exception as error:  # noqa: BLE001 — остаётся BM25
        return {}, f"эмбеддинги недоступны: {error}"

    candidates = [chunks[index] for index in ranked]
    stored, error = _embed_missing(target, candidates)
    best = max(lexical) or 1.0
    scores: dict[int, float] = {}

    for position, index in enumerate(ranked):
        vector = stored.get(candidates[position]["hash"])

        if vector is None:
            continue

        similarity = embeddings.cosine(query_vector, vector)
        norm = lexical[index] / best
        scores[index] = (
            VECTOR_WEIGHT * similarity + LEXICAL_WEIGHT * norm
        )

    if error:
        return scores, f"часть векторов не получена: {error}"

    return scores, f"эмбеддинги «{target[2]}»"


def _snippet(chunk: dict) -> str:
    """Одна строка текста фрагмента для ответа."""

    text = " ".join(str(chunk.get("text") or "").split())

    return text[:SNIPPET]


def _format(
    chunks: list[dict],
    scores: list[float],
    limit: int,
    method: str,
) -> str:
    """Ответ инструмента: путь, строка, символ и отрывок."""

    order = [
        index
        for index in sorted(
            range(len(chunks)),
            key=lambda item: -scores[item],
        )
        if scores[index] > 0
    ][:limit]

    if not order:
        return "По смыслу ничего не нашлось. Попробуй search_text."

    lines = [f"Найдено {len(order)} фрагментов ({method}):"]

    for index in order:
        chunk = chunks[index]
        lines.append(
            f"- {chunk['path']}:{chunk['line']} "
            f"[{chunk['kind']}] {chunk['name']} "
            f"({scores[index]:.2f})"
        )
        lines.append(f"  {_snippet(chunk)}")

    return "\n".join(lines)


def _path_weight(relative: str) -> float:
    """Тесты и документация чуть уступают коду проекта."""

    for prefix, weight in PATH_WEIGHTS:
        if str(relative).startswith(prefix):
            return weight

    return 1.0


def _scored(
    ranked: list[int],
    chunks: list[dict],
    lexical: list[float],
    hybrid: dict[int, float],
) -> list[float]:
    """Итоговые баллы: гибрид в 0..1 или чистый BM25, с весом пути."""

    if not hybrid:
        weighted = [
            value * _path_weight(chunk["path"])
            for value, chunk in zip(lexical, chunks)
        ]
        best = max(weighted, default=0.0) or 1.0

        return [value / best for value in weighted]

    best = max(lexical) or 1.0
    scores = [0.0] * len(chunks)

    for index in ranked:
        norm = lexical[index] / best
        scores[index] = hybrid.get(index, LEXICAL_WEIGHT * norm)

    return [
        value * _path_weight(chunk["path"])
        for value, chunk in zip(scores, chunks)
    ]


def find_relevant(
    root: Path,
    query: str,
    limit: int = DEFAULT_LIMIT,
    refresh: bool = False,
) -> ToolResult:
    """Ищет фрагменты по смыслу задачи, а не по точной строке."""

    text = str(query or "").strip()

    if len(tokens(text)) < 1:
        return ToolResult(
            False,
            "Нужен запрос словами: минимум одно слово длиннее одной буквы.",
        )

    document = load_chunks(root, refresh=refresh)
    chunks = document.get("chunks") or []

    if not chunks:
        return ToolResult(
            True,
            "Индекс пуст: в проекте не нашлось текстовых файлов.",
        )

    signature = str(document.get("signature") or _signature(chunks))
    lexical = _lexical(chunks, signature, text)
    ranked = sorted(
        range(len(chunks)),
        key=lambda item: -lexical[item],
    )[:CANDIDATES]
    hybrid, note = _hybrid(ranked, chunks, lexical, text)
    scores = _scored(ranked, chunks, lexical, hybrid)

    if hybrid:
        method = note or "слова и эмбеддинги"
    else:
        method = note or "только слова: эмбеддинги не настроены"

    limit = min(20, max(1, int(limit or DEFAULT_LIMIT)))

    return ToolResult(
        True,
        _format(chunks, scores, limit, method),
    )
