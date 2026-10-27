# Giperion/terminal/core/agent/knowledge.py                            v001
# База знаний: поиск по смыслу, разбор цитат и безопасное удаление.
# Последнее изменение: первый вариант — semantic.find_relevant + knowledge/.

import re
from pathlib import Path

from config import BASE_DIR

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
CITATION = re.compile(r"^- (?P<path>.+?):(?P<line>\d+) \[(?P<kind>[^\]]+)\]")
TITLE = re.compile(r"^(?P<title>.+?) \((?P<score>[0-9.]+)\)$")


def search(
    query: str,
    limit: int = 10,
    root: Path | None = None,
) -> list[dict]:
    """Ищет документы и возвращает цитаты с путём и строкой."""

    from terminal.core.agent import semantic

    text = str(query or "").strip()

    if not text:
        return []

    base = Path(root or BASE_DIR)
    result = semantic.find_relevant(base, text, max(1, int(limit)))
    citations = []
    current: dict | None = None

    for line in str(result.text or "").splitlines():
        match = CITATION.match(line)

        if match is not None:
            name = line[match.end():].strip()
            title_match = TITLE.match(name)
            current = {
                "path": match.group("path"),
                "line": int(match.group("line")),
                "kind": match.group("kind"),
                "title": (
                    title_match.group("title")
                    if title_match
                    else name
                ),
                "score": (
                    float(title_match.group("score"))
                    if title_match
                    else 0.0
                ),
                "snippet": "",
            }
            citations.append(current)
            continue

        if current is not None and line.startswith("  "):
            current["snippet"] += line.strip() + "\n"

    for item in citations:
        item["snippet"] = item["snippet"].strip()[:600]

    return citations


def remove(path: str, root: Path | None = None) -> bool:
    """Удаляет документ только внутри knowledge/."""

    base = Path(root or BASE_DIR).resolve()
    folder = (base / "knowledge").resolve()
    target = Path(path)

    if not target.is_absolute():
        target = base / target

    try:
        resolved = target.resolve()
        resolved.relative_to(folder)
    except (OSError, ValueError) as error:
        raise ValueError("Удалять можно только файлы knowledge/.") from error

    if not resolved.is_file() or resolved.suffix.lower() != ".md":
        raise ValueError("Документ не найден.")

    resolved.unlink()

    return True
