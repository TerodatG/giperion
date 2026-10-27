# Giperion/terminal/core/agent/pdf_text.py                             v001
# Текст скачанного PDF через необязательный pypdf.
# Последнее изменение: первый вариант — extract/from_files.

from pathlib import Path

MAX_TEXT = 12_000
MAX_PAGES = 200


def extract(path: Path) -> str:
    """Текст PDF или пустая строка, если pypdf нет/файл битый."""

    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(str(path))
    except Exception:  # noqa: BLE001 — библиотека бросает разное
        return ""

    parts = []

    for page in reader.pages[:MAX_PAGES]:
        try:
            text = (page.extract_text() or "").strip()
        except Exception:  # noqa: BLE001 — одна страница не ломает всё
            continue

        if text:
            parts.append(text)

    return "\n\n".join(parts)[:MAX_TEXT]


def from_files(downloads: list) -> str:
    """Первый непустой текст среди скачанных PDF."""

    for item in downloads:
        path = Path(str(item))

        if path.suffix.lower() != ".pdf" or not path.is_file():
            continue

        text = extract(path)

        if text:
            return text

    return ""
