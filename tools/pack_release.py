# Giperion/tools/pack_release.py                                     v001
# Собирает патч выпуска и добавляет его в каталог data/releases.json.
# Последнее изменение: первый вариант — архив, сумма и запись в каталог.

import argparse
import hashlib
import zipfile
from datetime import date
from pathlib import Path

from config import BASE_DIR
from shared.storage.json_store import read_json_object, write_json
from terminal.core.app_version import version_key
from terminal.core.update_service import (
    FEED_FILE,
    UPDATES_DIR,
    Release,
    patch_file_name,
)

# Готовые патчи лежат отдельно от скачанных: их раздаёт каталог выпусков.
FEED_PATCHES_DIR = UPDATES_DIR / "feed"


def _sha256(path: Path) -> str:
    """Считает контрольную сумму файла."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(256 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def build_patch(
    version: str,
    released: str,
    files: list[Path | str],
    output_dir: Path | str | None = None,
) -> Path:
    """Складывает файлы проекта в архив патча."""

    if not files:
        raise SystemExit("Нужен хотя бы один файл: --add путь")

    directory = Path(output_dir or FEED_PATCHES_DIR)
    directory.mkdir(parents=True, exist_ok=True)

    release = Release(version=version, date=released)
    target = directory / patch_file_name(release)

    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for item in sorted(files):
            source = Path(item)

            if not source.is_absolute():
                source = BASE_DIR / source

            if not source.is_file():
                raise SystemExit(f"Файл не найден: {source}")

            try:
                arcname = source.resolve().relative_to(
                    BASE_DIR.resolve()
                )
            except ValueError as error:
                raise SystemExit(
                    f"Файл вне проекта: {source}"
                ) from error

            archive.write(source, arcname.as_posix())

    return target


def publish_release(
    version: str,
    released: str,
    title: str,
    notes: list[str],
    files: list[Path | str],
    *,
    feed_file: Path | str | None = None,
    output_dir: Path | str | None = None,
) -> dict:
    """Собирает патч и записывает выпуск в каталог."""

    feed_path = Path(feed_file or FEED_FILE)

    patch_path = build_patch(version, released, files, output_dir)

    feed = read_json_object(feed_path)
    releases = [
        item
        for item in (feed.get("releases") or [])
        if str(item.get("version") or "") != version
    ]

    try:
        relative = patch_path.resolve().relative_to(
            BASE_DIR.resolve()
        ).as_posix()
    except ValueError:
        relative = patch_path.as_posix()

    entry = {
        "version": version,
        "date": released,
        "title": title,
        "notes": list(notes),
        "patch": relative,
        "sha256": _sha256(patch_path),
        "size": patch_path.stat().st_size,
    }

    releases.append(entry)
    releases.sort(
        key=lambda item: version_key(str(item.get("version") or "")),
        reverse=True,
    )

    feed.update(
        {
            "version": "v001",
            "app": "Giperion Terminal",
            "channel": str(feed.get("channel") or "stable"),
            "updated": date.today().isoformat(),
            "releases": releases,
        }
    )

    write_json(feed_path, feed, trailing_newline=True)

    return {
        **entry,
        "path": patch_path,
        "files": len(files),
    }


def main(argv: list[str] | None = None) -> int:
    """Разбирает аргументы и публикует выпуск."""

    parser = argparse.ArgumentParser(
        description=(
            "Собирает патч выпуска терминала и добавляет его в каталог "
            "data/releases.json."
        )
    )
    parser.add_argument("--version", required=True, help="например 1.1.0")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="дата выпуска ГГГГ-ММ-ДД (по умолчанию сегодня)",
    )
    parser.add_argument("--title", default="", help="название выпуска")
    parser.add_argument(
        "--note",
        action="append",
        default=[],
        help="пункт списка изменений (можно несколько раз)",
    )
    parser.add_argument(
        "--add",
        action="append",
        default=[],
        help="файл проекта для патча (можно несколько раз)",
    )
    parser.add_argument(
        "--feed",
        default="",
        help="другой каталог выпусков (по умолчанию data/releases.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="показать имя патча и выйти, ничего не записывая",
    )

    arguments = parser.parse_args(argv)

    if arguments.dry_run:
        release = Release(
            version=arguments.version,
            date=arguments.date,
        )
        print(f"Патч: {FEED_PATCHES_DIR / patch_file_name(release)}")
        print(f"Файлов: {len(arguments.add)}")

        return 0

    result = publish_release(
        arguments.version,
        arguments.date,
        arguments.title,
        arguments.note,
        arguments.add,
        feed_file=arguments.feed or None,
    )

    print(f"Выпуск {result['version']} от {result['date']} опубликован.")
    print(f"Патч: {result['patch']}")
    print(f"Размер: {result['size']} Б · файлов: {result['files']}")
    print(f"sha256: {result['sha256']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
