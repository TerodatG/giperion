# Giperion/tools/verify_release.py                                    v001
# Проверка артефактов релиза и SHA256SUMS.
# Последнее изменение: первый вариант — verify/hashes.

import argparse
import hashlib
import sys
from pathlib import Path

SUFFIXES = (".zip", ".exe", ".deb", ".AppImage", ".dmg", ".gz")

# Windows-консоль по умолчанию cp1252: русские сообщения роняют проверку.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(256 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def artifacts(folder: Path) -> list[Path]:
    """Файлы-артефакты в папке."""

    base = Path(folder)

    return [
        path
        for path in sorted(base.iterdir())
        if path.is_file()
        and (
            path.suffix in SUFFIXES
            or path.name.endswith(".tar.gz")
        )
    ]


def verify(folder: Path) -> list[str]:
    """Ошибки: нет файла, нет суммы, сумма не совпала."""

    base = Path(folder)
    sums = base / "SHA256SUMS"
    errors = []

    if not sums.is_file():
        return ["нет SHA256SUMS"]

    expected = {}

    for line in sums.read_text(encoding="utf-8").splitlines():
        parts = line.split(None, 1)

        if len(parts) != 2:
            continue

        expected[parts[1].strip()] = parts[0].strip()

    for path in artifacts(base):
        if path.name not in expected:
            errors.append(f"нет суммы: {path.name}")
            continue

        if sha256(path) != expected[path.name]:
            errors.append(f"сумма не совпала: {path.name}")

    for name in expected:
        if not (base / name).is_file():
            errors.append(f"нет файла: {name}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Проверить артефакты релиза и SHA256SUMS.",
    )
    parser.add_argument("--folder", default="dist")
    args = parser.parse_args()
    folder = Path(args.folder)
    errors = verify(folder)

    if errors:
        for error in errors:
            print("ОШИБКА ·", error)

        return 1

    print("OK · артефактов:", len(artifacts(folder)))

    return 0


if __name__ == "__main__":
    sys.exit(main())
