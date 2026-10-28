# Giperion/tools/update_feed.py                                       v001
# Каталог выпусков для автообновления: патч-архив и releases-<платформа>.json.
#
# Патч — это содержимое `_internal` (код и данные приложения), упакованное
# без внешней папки: update_service распаковывает его поверх BASE_DIR.
#
# Пример:
#   python -m tools.update_feed pack --app dist/Giperion \
#       --out dist/patch.zip
#   python -m tools.update_feed feed --version 1.0.0 --target windows \
#       --patch dist/patch.zip --url https://... --out dist/releases-windows.json

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

APP_NAME = "Giperion Terminal"

# Что не кладём в патч: рабочие папки, которых в сборке быть не должно.
SKIP_PARTS = {"logs", "updates", "archive", "__pycache__"}


def sha256(path: Path) -> str:
    """Считает SHA-256 файла."""

    digest = hashlib.sha256()

    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(256 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def pack_patch(app: Path, target: Path) -> Path:
    """Пакует содержимое `_internal` в zip без внешней папки."""

    internal = Path(app) / "_internal"

    if not internal.is_dir():
        raise SystemExit(f"нет папки _internal: {internal}")

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(internal.rglob("*")):
            if not path.is_file():
                continue

            relative = path.relative_to(internal)

            if relative.parts and relative.parts[0] in SKIP_PARTS:
                continue

            archive.write(path, relative.as_posix())

    print("+ патч", target, f"{target.stat().st_size // (1024 * 1024)} МБ")

    return target


def build_feed(
    version: str,
    target: str,
    patch: Path,
    url: str,
    released: str = "",
    title: str = "",
    notes: list[str] | None = None,
    channel: str = "stable",
) -> dict:
    """Собирает каталог выпусков с одной записью."""

    patch = Path(patch)

    return {
        "version": "v001",
        "app": APP_NAME,
        "channel": channel,
        "updated": released or date.today().isoformat(),
        "releases": [
            {
                "version": version,
                "date": released or date.today().isoformat(),
                "title": title or f"Выпуск {version}",
                "notes": list(notes or []),
                "patch": url,
                "sha256": sha256(patch),
                "size": patch.stat().st_size,
            }
        ],
        "target": target,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Каталог выпусков и патч для автообновления.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pack = sub.add_parser("pack", help="упаковать _internal в патч")
    pack.add_argument("--app", default="dist/Giperion")
    pack.add_argument("--out", required=True)

    feed = sub.add_parser("feed", help="собрать releases-<платформа>.json")
    feed.add_argument("--version", required=True)
    feed.add_argument("--target", required=True)
    feed.add_argument("--patch", required=True)
    feed.add_argument("--url", required=True)
    feed.add_argument("--out", required=True)
    feed.add_argument("--released", default="")
    feed.add_argument("--title", default="")
    feed.add_argument("--note", action="append", default=[])

    feeds = sub.add_parser(
        "feeds",
        help="собрать каталоги по патчам patch-<платформа>.zip",
    )
    feeds.add_argument("--dist", default="dist")
    feeds.add_argument("--version", required=True)
    feeds.add_argument("--base-url", required=True)
    feeds.add_argument("--released", default="")
    feeds.add_argument("--title", default="")

    check = sub.add_parser("check", help="проверить канал обновлений")
    check.add_argument("--feed", default="")

    args = parser.parse_args()

    if args.command == "check":
        from terminal.core.update_service import check_updates

        result = check_updates(args.feed)

        if result.error:
            print("ОШИБКА:", result.error)

            return 1

        print(f"установлено: {result.current} · канал: {result.source}")

        if not result.new_releases:
            print("обновлений нет")

            return 0

        for release in result.new_releases:
            print(f"+ {release.version} от {release.date}")

            if release.patch:
                print(f"  патч: {release.patch}")

        return 0

    if args.command == "pack":
        pack_patch(Path(args.app), Path(args.out))

        return 0

    if args.command == "feeds":
        dist = Path(args.dist)
        built = 0

        for patch in sorted(dist.glob("patch-*.zip")):
            target = patch.stem.removeprefix("patch-")
            document = build_feed(
                version=args.version,
                target=target,
                patch=patch,
                url=f"{args.base_url.rstrip('/')}/{patch.name}",
                released=args.released,
                title=args.title,
            )
            out = dist / f"releases-{target}.json"
            out.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print("+ каталог", out)
            built += 1

        if not built:
            raise SystemExit("не найдено ни одного patch-*.zip")

        return 0

    document = build_feed(
        version=args.version,
        target=args.target,
        patch=Path(args.patch),
        url=args.url,
        released=args.released,
        title=args.title,
        notes=args.note,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("+ каталог", out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
