# Giperion/tools/plugin_sign.py                                       v001
# Подпись и проверка плагина: HMAC-SHA256 по файлам.
# Последнее изменение: первый вариант — ключ, подпись, проверка.

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path

from config import DATA_DIR

KEY_FILE = DATA_DIR / "plugin_signing.key"
SIGNATURE = "signature.json"
EXCLUDE = {SIGNATURE}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file()
        and path.name not in EXCLUDE
        and "__pycache__" not in path.parts
    )


def _key(path: Path, create: bool = False) -> bytes:
    if not path.exists() and create:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32), encoding="utf-8")

        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ValueError(f"Ключ не найден: {path}") from error

    if len(text) < 32:
        raise ValueError("Ключ слишком короткий.")

    return text.encode("utf-8")


def _signature(files: dict[str, str], key: bytes) -> str:
    body = json.dumps(files, ensure_ascii=False, sort_keys=True)

    return hmac.new(
        key,
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def sign(folder: Path, key_file: Path | None = None) -> Path:
    """Пишет signature.json рядом с манифестом."""

    from tools.plugin_install import validate

    base = Path(folder)
    validate(base)
    key = _key(key_file or KEY_FILE, create=True)
    files = {
        path.relative_to(base).as_posix(): _hash(path)
        for path in _files(base)
    }
    payload = {
        "algorithm": "hmac-sha256",
        "files": files,
        "signature": _signature(files, key),
    }
    target = base / SIGNATURE
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return target


def verify(
    folder: Path,
    key_file: Path | None = None,
) -> tuple[bool, str]:
    """Проверяет подпись и хеши файлов."""

    base = Path(folder)
    target = base / SIGNATURE

    if not target.is_file():
        return False, "нет signature.json"

    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        key = _key(key_file or KEY_FILE)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return False, str(error)

    files = payload.get("files")

    if not isinstance(files, dict):
        return False, "в подписи нет files"

    actual = {
        path.relative_to(base).as_posix(): _hash(path)
        for path in _files(base)
    }

    if actual != files:
        return False, "файлы изменились после подписи"

    expected = _signature(files, key)

    if not hmac.compare_digest(expected, str(payload.get("signature"))):
        return False, "подпись не совпадает"

    return True, "подпись верна"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Подписать плагин или проверить подпись.",
    )
    parser.add_argument("folder")
    parser.add_argument("--key", default=str(KEY_FILE))
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--gen-key", action="store_true")
    args = parser.parse_args()

    folder = Path(args.folder)
    key_file = Path(args.key)

    try:
        if args.gen_key:
            _key(key_file, create=True)
            print("Ключ:", key_file)
            return 0

        if args.verify:
            ok, message = verify(folder, key_file)
            print(("OK · " if ok else "ОШИБКА · ") + message)

            return 0 if ok else 1

        target = sign(folder, key_file)
        ok, message = verify(folder, key_file)
    except ValueError as error:
        print("Не подписано:", error)
        return 1

    print("Подпись:", target)
    print("Проверка:", message if ok else "ошибка")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
