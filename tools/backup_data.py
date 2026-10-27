# Giperion/tools/backup_data.py                                       v001
# Резервная копия data/ и восстановление без path traversal.
# Последнее изменение: первый вариант — zip, manifest, секреты по флагу.

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from config import DATA_DIR

MAX_FILES = 100_000
MAX_UNPACKED = 2_000_000_000
SECRETS = {
    "agent_api_token",
    "audit_export.key",
    "plugin_signing.key",
}


def _files(root: Path, with_secrets: bool) -> list[Path]:
    """Файлы data/ без кешей, временных и (по умолчанию) секретов."""

    result = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(root)

        if "__pycache__" in relative.parts:
            continue

        if relative.parts[0] == "backups":
            continue

        if path.suffix in (".tmp", ".pyc"):
            continue

        if not with_secrets and path.name in SECRETS:
            continue

        result.append(path)

        if len(result) >= MAX_FILES:
            break

    return result


def create(target: Path | None = None, with_secrets: bool = False) -> Path:
    """Создаёт zip с data/ и manifest.json."""

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = Path(target or DATA_DIR / "backups" / (
        f"giperion-data-{stamp}.zip"
    ))
    output.parent.mkdir(parents=True, exist_ok=True)
    files = _files(Path(DATA_DIR), with_secrets)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "files": [path.relative_to(DATA_DIR).as_posix() for path in files],
        "secrets": bool(with_secrets),
    }

    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in files:
            archive.write(
                path,
                path.relative_to(DATA_DIR).as_posix(),
            )

        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2),
        )

    return output


def _safe(name: str) -> bool:
    """Относительный путь без .., абсолютных дисков и NUL."""

    path = PurePosixPath(name)

    if path.is_absolute() or ".." in path.parts:
        return False

    return not any(part in ("", ".") for part in path.parts)


def restore(
    archive: Path,
    target: Path | None = None,
    force: bool = False,
) -> int:
    """Распаковывает архив; существующие файлы без force не трогает."""

    root = Path(target or DATA_DIR)
    root.mkdir(parents=True, exist_ok=True)
    restored = 0
    unpacked = 0

    try:
        handle = zipfile.ZipFile(archive)
    except (OSError, zipfile.BadZipFile) as error:
        raise ValueError(f"Битый архив: {error}") from error

    with handle as source:
        infos = source.infolist()

        if len(infos) > MAX_FILES:
            raise ValueError("В архиве слишком много файлов.")

        for info in infos:
            if info.is_dir() or info.filename == "manifest.json":
                continue

            if not _safe(info.filename):
                raise ValueError(
                    f"Небезопасный путь в архиве: {info.filename}"
                )

            unpacked += info.file_size

            if unpacked > MAX_UNPACKED:
                raise ValueError("Архив больше допустимого размера.")

            destination = root / info.filename

            if destination.exists() and not force:
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)

            with source.open(info) as src:
                destination.write_bytes(src.read())

            restored += 1

    return restored


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Резервная копия data/ и восстановление.",
    )
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--restore", default="")
    parser.add_argument("--target", default="")
    parser.add_argument("--with-secrets", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    try:
        if args.restore:
            count = restore(
                Path(args.restore),
                target=Path(args.target) if args.target else None,
                force=args.force,
            )
            print(f"Восстановлено файлов: {count}")
            return 0

        path = create(
            Path(args.target) if args.target else None,
            with_secrets=args.with_secrets,
        )
    except ValueError as error:
        print("Ошибка:", error)
        return 1

    print("Резервная копия:", path)
    print(
        "Секреты включены." if args.with_secrets else
        "Секреты (токены и ключи) не включены; добавьте --with-secrets."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
