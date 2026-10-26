# Giperion/tools/clean_caches.py                                      v001
# Очистка кешей агента: фрагменты, векторы и индекс символов.
# Последнее изменение: первый вариант — --check, --yes, выборочные флаги.

import argparse
import sys
from pathlib import Path

from config import DATA_DIR

TARGETS = (
    ("фрагменты", "agent_semantic.json"),
    ("векторы", "agent_vectors.db"),
    ("векторы (wal)", "agent_vectors.db-wal"),
    ("векторы (shm)", "agent_vectors.db-shm"),
    ("векторы (старый JSON)", "agent_vectors.json"),
    ("индекс символов", "agent_index.json"),
)


def targets(keep_vectors: bool = False, keep_index: bool = False) -> list:
    """Файлы кеша по выбранным флагам."""

    found = []

    for title, name in TARGETS:
        if keep_vectors and name.startswith("agent_vectors"):
            continue

        if keep_index and name == "agent_index.json":
            continue

        path = DATA_DIR / name

        if path.exists():
            found.append((title, path))

    return found


def _size(path: Path) -> str:
    try:
        value = path.stat().st_size
    except OSError:
        return "—"

    if value >= 1024 * 1024:
        return f"{value / 1024 / 1024:.1f} МБ"

    return f"{value / 1024:.0f} КБ"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Показать и удалить кеши смыслового поиска.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="действительно удалить (без флага — только показать)",
    )
    parser.add_argument(
        "--keep-vectors",
        action="store_true",
        help="оставить кеш векторов",
    )
    parser.add_argument(
        "--keep-index",
        action="store_true",
        help="оставить индекс символов",
    )
    args = parser.parse_args()

    found = targets(
        keep_vectors=args.keep_vectors,
        keep_index=args.keep_index,
    )

    if not found:
        print("Кешей нет — всё и так чисто.")
        return 0

    total = 0

    print("Кеши агента:")
    for title, path in found:
        try:
            total += path.stat().st_size
        except OSError:
            pass

        print(f"  {title:22} {_size(path):>8}  {path.name}")

    print(f"  {'итого':22} {total / 1024 / 1024:>7.1f} МБ")

    if not args.yes:
        print()
        print("Ничего не удалено. Добавьте --yes, чтобы очистить.")
        return 0

    removed = 0

    for _title, path in found:
        try:
            path.unlink()
            removed += 1
        except OSError as error:
            print(f"  не удалось удалить {path.name}: {error}")

    print()
    print(f"Удалено файлов: {removed} из {len(found)}.")
    print("Индекс перестроится при следующем поиске.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
