# Giperion/app/skills/file_reader.py                               v001
# Чтение текстового файла для показа в чате.
# Последнее изменение: первый вариант — UTF-8, UTF-8 с BOM и Windows-1251.

from pathlib import Path

# Больше этого файла в чат не читаем: защита от случайной гигантской книги.
MAX_FILE_BYTES = 512 * 1024

# Сколько символов файла показываем в истории чата.
MAX_TEXT_CHARS = 8000

# Кодировки пробуем по очереди: UTF-8 встречается чаще, cp1251 — в старых
# текстовых файлах Windows.
ENCODINGS = ("utf-8-sig", "utf-8", "cp1251")

# Фильтр для окна выбора файла.
TEXT_FILE_FILTER = (
    "Текстовые файлы (*.txt *.md *.py *.json *.csv *.log *.ini "
    "*.cfg *.xml *.html *.css *.js *.ts *.yaml *.yml *.toml);;"
    "Все файлы (*.*)"
)


class FileReadError(ValueError):
    """Файл не удалось прочитать как текст."""


def read_text_file(path: str | Path) -> dict:
    """Читает текстовый файл и возвращает данные для показа в чате."""

    file_path = Path(path)

    if not file_path.is_file():
        raise FileReadError("файл не найден")

    try:
        size = file_path.stat().st_size
    except OSError as error:
        raise FileReadError(str(error)) from error

    if size > MAX_FILE_BYTES:
        limit = MAX_FILE_BYTES // 1024

        raise FileReadError(
            f"файл больше {limit} КБ — читать его целиком небезопасно"
        )

    try:
        data = file_path.read_bytes()
    except OSError as error:
        raise FileReadError(str(error)) from error

    # Нулевой байт — верный признак двоичного файла, а не текста.
    if b"\x00" in data:
        raise FileReadError(
            "похоже, это двоичный файл, а не текст"
        )

    text = None
    encoding = ""

    for candidate in ENCODINGS:
        try:
            text = data.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue

    if text is None:
        raise FileReadError(
            "не удалось определить кодировку текста"
        )

    # В окне чата переводы строк всегда одинаковые.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    truncated = len(text) > MAX_TEXT_CHARS

    return {
        "name": file_path.name,
        "path": str(file_path),
        "text": text[:MAX_TEXT_CHARS],
        "full_length": len(text),
        "truncated": truncated,
        "encoding": encoding,
        "size": size,
    }
