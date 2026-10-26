# Giperion/tools/build_semantic_index.py                               v001
# Глубокий индекс смыслового поиска: векторы для всех фрагментов.
# Последнее изменение: первый вариант — батчи, --check, --limit.

import argparse
import sys
import time

from config import BASE_DIR
from terminal.core.agent import embeddings, semantic


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Считает эмбеддинги для всех фрагментов проекта, чтобы "
            "find_relevant искал по смыслу, а не только по словам."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="только показать покрытие векторами",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=32,
        help="сколько фрагментов отправлять за один запрос",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="обработать только первые N фрагментов",
    )

    return parser


def _progress(done: int, total: int) -> None:
    print(f"\r  векторы: {done}/{total}", end="", flush=True)


def _show_stats() -> int:
    stats = semantic.vector_stats(BASE_DIR)

    if not stats["model"]:
        print(
            "Локальный провайдер с /embeddings не найден: укажите "
            "локальный адрес в «Провайдере» и загрузите модель "
            "эмбеддингов."
        )

        return 1

    print("Модель:", stats["model"])
    print(
        f"Покрытие: {stats['covered']}/{stats['total']} фрагментов"
    )

    return 0


def _build(batch: int, limit: int) -> int:
    document = semantic.load_chunks(BASE_DIR)
    chunks = document.get("chunks") or []

    if limit > 0:
        chunks = chunks[:limit]

    if not chunks:
        print("Фрагментов не найдено.")
        return 1

    started = time.monotonic()

    try:
        added, total = semantic.cache_vectors(
            chunks,
            batch=batch,
            progress=_progress,
        )
    except embeddings.EmbeddingError as error:
        print()
        print("Не получилось:", error)
        return 1

    print()
    print(
        f"Добавлено векторов: {added} из {total} "
        f"за {time.monotonic() - started:.1f} с"
    )

    return _show_stats()


def main() -> int:
    args = _parser().parse_args()

    if args.check:
        return _show_stats()

    return _build(int(args.batch), int(args.limit))


if __name__ == "__main__":
    sys.exit(main())
