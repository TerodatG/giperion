# Giperion/tools/knowledge_add.py                                     v001
# Добавляет заметку или документ в knowledge/ для смыслового поиска.
# Последнее изменение: первый вариант — файл/текст, слаг и лимит.

import argparse
import hashlib
import io
import re
import sys
import zipfile
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

from config import BASE_DIR

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
MAX_BYTES = 200_000
SUFFIXES = {
    ".md",
    ".txt",
    ".rst",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".html",
    ".htm",
    ".pdf",
    ".docx",
}
TEXT_SUFFIXES = {".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".csv"}
NAME_RE = re.compile(r"[^\w-]+", re.UNICODE)
HASH_RE = re.compile(r"^Хеш:\s*([0-9a-f]{40})$", re.MULTILINE)


class _TextParser(HTMLParser):
    """Достаёт текст из HTML, пропуская script/style."""

    SKIP = {"script", "style", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs) -> None:
        if tag.lower() in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag) -> None:
        if tag.lower() in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data) -> None:
        if not self._skip:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join(" ".join(self.parts).split())


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


def _digest(body: str) -> str:
    """Хеш нормализованного текста для дедупликации."""

    clean = "\n".join(
        line.rstrip() for line in body.strip().splitlines()
    )

    return hashlib.sha1(clean.encode("utf-8")).hexdigest()


def _existing(digest: str) -> Path | None:
    """Документ с тем же хешем, если он уже есть."""

    if not KNOWLEDGE_DIR.is_dir():
        return None

    for path in KNOWLEDGE_DIR.glob("*.md"):
        try:
            head = path.read_text(encoding="utf-8")[:2_000]
        except OSError:
            continue

        match = HASH_RE.search(head)

        if match is not None and match.group(1) == digest:
            return path

    return None


def _html_text(path: Path) -> str:
    """Текст HTML без разметки и скриптов."""

    parser = _TextParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    parser.close()

    return parser.text()


def _docx_text(path: Path) -> str:
    """Текст DOCX из word/document.xml."""

    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, OSError, zipfile.BadZipFile) as error:
        raise ValueError(f"Не удалось прочитать DOCX: {error}") from error

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as error:
        raise ValueError(f"Битый DOCX: {error}") from error

    parts = []

    for paragraph in root.iter():
        if not paragraph.tag.endswith("}p"):
            continue

        text = "".join(
            node.text or ""
            for node in paragraph.iter()
            if node.tag.endswith("}t")
        ).strip()

        if text:
            parts.append(text)

    return "\n".join(parts)


def _pdf_text(path: Path) -> str:
    """Текст PDF через необязательный pypdf."""

    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise ValueError(
            "Для PDF установите pypdf: python -m pip install pypdf"
        ) from error

    try:
        reader = PdfReader(io.BytesIO(path.read_bytes()))
    except Exception as error:  # noqa: BLE001 — библиотека бросает разное
        raise ValueError(f"Битый PDF: {error}") from error

    parts = []

    for page in reader.pages[:200]:
        text = (page.extract_text() or "").strip()

        if text:
            parts.append(text)

    return "\n\n".join(parts)


def _read_document(path: Path) -> str:
    """Текст поддерживаемого документа."""

    suffix = path.suffix.lower()

    if suffix in TEXT_SUFFIXES:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise ValueError(
                f"Не удалось прочитать файл: {error}"
            ) from error

    if suffix in (".html", ".htm"):
        return _html_text(path)

    if suffix == ".docx":
        return _docx_text(path)

    if suffix == ".pdf":
        return _pdf_text(path)

    raise ValueError(
        "Поддерживаются: " + ", ".join(sorted(SUFFIXES))
    )


def add_text(
    text: str,
    title: str = "note",
    tags: list[str] | None = None,
) -> Path:
    """Сохраняет текст в knowledge/ с заголовком, тегами и хешем."""

    body = unescape(str(text or "")).strip()

    if not body:
        raise ValueError("Текст пустой.")

    if len(body.encode("utf-8")) > MAX_BYTES:
        raise ValueError(
            f"Документ больше {MAX_BYTES // 1000} КБ."
        )

    digest = _digest(body)
    duplicate = _existing(digest)

    if duplicate is not None:
        return duplicate

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
    header.append("Хеш: " + digest)
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
    """Импортирует текст, HTML, PDF или DOCX в knowledge/."""

    path = Path(source)

    if not path.is_file():
        raise ValueError(f"Файл не найден: {path}")

    if path.suffix.lower() not in SUFFIXES:
        raise ValueError(
            "Поддерживаются форматы: "
            + ", ".join(sorted(SUFFIXES))
        )

    text = _read_document(path)

    return add_text(
        text,
        title or path.stem,
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
