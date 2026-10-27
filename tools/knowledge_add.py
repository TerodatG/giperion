# Giperion/tools/knowledge_add.py                                     v001
# Добавляет заметку или документ в knowledge/ для смыслового поиска.
# Последнее изменение: первый вариант — файл/текст, слаг и лимит.

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

from config import BASE_DIR

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
MAX_BYTES = 200_000
SUFFIXES = {".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".csv"}
NAME_RE = re.compile(r"[^\w-]+", re.UNICODE)


def _slug(name: str) -> str:
    """Безопасное имя файла из заголовка."""

    source = Path(name).stem if name else "note"
    text = NAME_RE.sub("-", source.lower()).strip("-")

    return (text or "note")[:60]


def _destination(title: str, suffix: str = ".md") -> Path:
    """Свободное имя в knowledge/."""

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{stamp}-{_slug(title)}"
    candidate = KNOWLEDGE_DIR / (base + suffix)
    index = 2

    while candidate.exists():
        candidate = KNOWLEDGE_DIR / f"{base}-{index}{suffix}"
        index += 1

    return candidate


def add_text(
    text: str,
    title: str = "note",
    tags: list[str] | None = None,
) -> Path:
    """Сохраняет текст в knowledge/ с заголовком и тегами."""

    body = str(text or "").strip()

    if not body:
        raise ValueError("Текст пустой.")

    if len(body.encode("utf-8")) > MAX_BYTES:
        raise ValueError(
            f"Документ больше {MAX_BYTES // 1000} КБ."
        )

    tags = [
        str(tag).strip().lstrip("#")
        for tag in (tags or [])
        if str(tag).strip()
    ]
    header = [f"# {title}"]
    added = datetime.now().strftime("%Y-%m-%d")

    if tags:
        header.append("Теги: " + ", ".join(tags))

    header.append("Добавлено: " + added)
    content = "\n".join(header) + "\n\n" + body

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    path = _destination(title)
    path.write_text(content + "\n", encoding="utf-8")

    return path


def add_file(
    source: Path,
    title: str = "",
    tags: list[str] | None = None,
) -> Path:
    """Копирует текстовый файл в knowledge/."""

    path = Path(source)

    if not path.is_file():
        raise ValueError(f"Файл не найден: {path}")

    if path.suffix.lower() not in SUFFIXES:
        raise ValueError(
            "Поддерживаются текстовые форматы: "
            + ", ".join(sorted(SUFFIXES))
        )

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise ValueError(
            f"Не удалось прочитать файл: {error}"
        ) from error

    return add_text(
        text,
        title or path.name,
        tags=tags,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Добавить документ в knowledge/. Он попадёт в смысловой "
            "индекс при следующей пересборке."
        ),
    )
    parser.add_argument("source", nargs="?", default="")
    parser.add_argument("--text", default="")
    parser.add_argument("--title", default="")
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="тег (можно несколько раз)",
    )
    args = parser.parse_args()

    try:
        if args.text:
            path = add_text(
                args.text,
                args.title or "note",
                tags=args.tag,
            )
        elif args.source:
            path = add_file(
                Path(args.source),
                args.title,
                tags=args.tag,
            )
        else:
            parser.error("нужен файл или --text")
            return 2
    except ValueError as error:
        print("Не добавлено:", error)
        return 1

    print("Добавлено:", path.relative_to(BASE_DIR).as_posix())
    print(
        "Смысловой индекс подхватит при следующем поиске; "
        "для полного покрытия — python -m tools.build_semantic_index."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
