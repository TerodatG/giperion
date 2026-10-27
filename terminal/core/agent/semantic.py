# Giperion/terminal/core/agent/semantic.py                             v002
# Смысловой поиск: BM25 по фрагментам и переранжирование эмбеддингами.
# Последнее изменение: фрагменты и токены вынесены в semantic_index/text.

from collections import Counter
from pathlib import Path

from config import DATA_DIR
from terminal.core.agent import embeddings, semantic_index, vector_store
from terminal.core.agent.protocol import ToolResult
from terminal.core.agent.semantic_text import (
    index_tokens,
    stem,  # noqa: F401 — реэкспорт для тестов
    tokens,
)

CACHE_FILE = DATA_DIR / "agent_semantic.json"
VECTOR_FILE = DATA_DIR / "agent_vectors.db"
CANDIDATES = 80
VECTOR_HITS = 80
MAX_EMBED_PER_CALL = 120
MAX_VECTORS = 6000
DEFAULT_LIMIT = 8
SNIPPET = 200
K1 = 1.5
B = 0.75
VECTOR_WEIGHT = 0.15
LEXICAL_WEIGHT = 0.85
VECTOR_ONLY_WEIGHT = 0.3
RERANK_DEPTH = 10
PATH_WEIGHTS = (("tests/", 0.4), ("docs/", 0.65), ("model/tests/", 0.3))

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
    """Векторы из SQLite для текущей модели."""

    key = ("file", model)
    cached = _VECTORS.get(key)

    if cached is not None:
        return cached

    stored = vector_store.load(VECTOR_FILE, model)
    _VECTORS[key] = stored

    return stored


def _save_vectors(model: str, stored: dict[str, list[float]]) -> None:
    """Сохраняет векторы, вытесняя самые старые сверх лимита."""

    if len(stored) > MAX_VECTORS:
        keep = list(stored.items())[-MAX_VECTORS:]
        stored.clear()
        stored.update(keep)

    vector_store.save(
        VECTOR_FILE,
        model,
        stored,
        limit=MAX_VECTORS,
    )


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

    for chunk, vector in zip(missing, vectors, strict=False):
        stored[chunk["hash"]] = [
            round(float(value), 4) for value in vector
        ]

    _save_vectors(model, stored)

    return stored, ""


def _cosines(
    chunks: list[dict],
    query_vector: list[float],
    stored: dict[str, list[float]],
) -> dict[int, float]:
    """Косинус запроса и всех фрагментов, у которых есть вектор."""

    values: dict[int, float] = {}

    for index, chunk in enumerate(chunks):
        vector = stored.get(chunk["hash"])

        if vector is not None:
            values[index] = embeddings.cosine(query_vector, vector)

    return values


def _normalized(values: dict[int, float]) -> dict[int, float]:
    """Min-max по выдаче: убирает высокий «фон» косинуса."""

    if not values:
        return {}

    low = min(values.values())
    high = max(values.values())
    span = high - low

    if span < 0.05:
        return {index: 0.5 for index in values}

    return {
        index: (value - low) / span
        for index, value in values.items()
    }


def _hybrid(
    ranked: list[int],
    chunks: list[dict],
    lexical: list[float],
    query: str,
) -> tuple[dict[int, float], str]:
    """BM25-кандидаты плюс лучшие по вектору; пусто — эмбеддинги недоступны."""

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
    cosines = _cosines(chunks, query_vector, stored)
    vector_hits = sorted(
        cosines,
        key=lambda index: -cosines[index],
    )[:VECTOR_HITS]
    merged = list(dict.fromkeys(list(ranked) + vector_hits))
    normalized = _normalized(
        {index: cosines[index] for index in merged if index in cosines}
    )
    best = max(lexical) or 1.0
    dense = set(ranked[:RERANK_DEPTH])
    scores: dict[int, float] = {}

    for index in merged:
        similarity = normalized.get(index, 0.0)
        norm = lexical[index] / best

        if index in dense:
            scores[index] = (
                LEXICAL_WEIGHT * norm + VECTOR_WEIGHT * similarity
            )
        elif index in ranked:
            scores[index] = LEXICAL_WEIGHT * norm
        else:
            scores[index] = VECTOR_ONLY_WEIGHT * similarity

    covered = sum(
        1 for chunk in chunks if chunk["hash"] in stored
    )
    note = (
        f"эмбеддинги «{target[2]}», "
        f"{covered}/{len(chunks)} фрагментов"
    )

    if error:
        return scores, f"часть векторов не получена: {error}; {note}"

    return scores, note


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
    chunks: list[dict],
    lexical: list[float],
    hybrid: dict[int, float],
) -> list[float]:
    """Итоговые баллы: гибрид в 0..1 или чистый BM25, с весом пути."""

    if not hybrid:
        weighted = [
            value * _path_weight(chunk["path"])
            for value, chunk in zip(lexical, chunks, strict=False)
        ]
        best = max(weighted, default=0.0) or 1.0

        return [value / best for value in weighted]

    scores = [0.0] * len(chunks)

    for index, value in hybrid.items():
        scores[index] = value

    return [
        value * _path_weight(chunk["path"])
        for value, chunk in zip(scores, chunks, strict=False)
    ]


def cache_vectors(
    chunks: list[dict],
    batch: int = 32,
    progress=None,
) -> tuple[int, int]:
    """Считает векторы для всех фрагментов пачками; возвращает (новых, всего).

    Нужен локальный провайдер. Кеш пишется по ходу, поэтому обрыв не
    теряет уже посчитанное.
    """

    target = embeddings.client()

    if target is None:
        raise embeddings.EmbeddingError(
            "Нужен локальный провайдер с /embeddings."
        )

    model = target[2]
    stored = _load_vectors(model)
    missing = [
        chunk for chunk in chunks
        if chunk["hash"] not in stored
    ]
    total = len(missing)
    added = 0
    saved_at = 0
    size = max(1, int(batch))

    for start in range(0, total, size):
        part = missing[start:start + size]
        vectors = embeddings.embed(
            [chunk["payload"] for chunk in part],
            target=target,
            timeout=180,
        )

        for chunk, vector in zip(part, vectors, strict=False):
            stored[chunk["hash"]] = [
                round(float(value), 4) for value in vector
            ]

        added += len(part)

        if progress is not None:
            progress(added, total)

        if added - saved_at >= size * 5:
            _save_vectors(model, stored)
            saved_at = added

    _save_vectors(model, stored)

    return added, total


def vector_stats(root: Path) -> dict:
    """Сколько фрагментов уже имеет вектор."""

    document = load_chunks(root)
    chunks = document.get("chunks") or []
    target = embeddings.client()
    stats = {
        "total": len(chunks),
        "covered": 0,
        "model": "",
    }

    if target is None:
        return stats

    stored = _load_vectors(target[2])
    stats["covered"] = sum(
        1 for chunk in chunks if chunk["hash"] in stored
    )
    stats["model"] = target[2]

    return stats


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
    scores = _scored(chunks, lexical, hybrid)

    if hybrid:
        method = note or "слова и эмбеддинги"
    else:
        method = note or "только слова: эмбеддинги не настроены"

    limit = min(20, max(1, int(limit or DEFAULT_LIMIT)))

    return ToolResult(
        True,
        _format(chunks, scores, limit, method),
    )
