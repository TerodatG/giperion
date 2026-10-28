# Giperion/tests/test_update_feed.py                                  v001
# Каталог выпусков и патч-архив для автообновления.

import json
import zipfile
from pathlib import Path

from terminal.core import update_channel, update_service
from tools import update_feed


def _app(tmp_path: Path) -> Path:
    """Собирает миниатюрную one-dir сборку."""

    app = tmp_path / "Giperion"
    internal = app / "_internal"

    (internal / "pkg").mkdir(parents=True)
    (internal / "pkg" / "module.py").write_text("x = 1\n", encoding="utf-8")
    (internal / "data").mkdir()
    (internal / "data" / "intents.json").write_text("{}", encoding="utf-8")
    (app / "Giperion.exe").write_bytes(b"exe")

    return app


def test_pack_patch_keeps_internal_only(tmp_path) -> None:
    """Патч содержит _internal без пользовательских папок."""

    app = _app(tmp_path)
    target = tmp_path / "patch.zip"

    update_feed.pack_patch(app, target)

    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())

    assert "pkg/module.py" in names
    assert "data/intents.json" in names
    assert "Giperion.exe" not in names


def test_build_feed_has_checksum_and_url(tmp_path) -> None:
    """Каталог ссылается на патч и хранит его сумму."""

    app = _app(tmp_path)
    patch = tmp_path / "patch.zip"

    update_feed.pack_patch(app, patch)

    document = update_feed.build_feed(
        version="1.2.3",
        target="windows",
        patch=patch,
        url="https://example.org/patch.zip",
        released="2026-10-29",
    )

    release = document["releases"][0]

    assert release["version"] == "1.2.3"
    assert release["patch"] == "https://example.org/patch.zip"
    assert release["sha256"] == update_feed.sha256(patch)
    assert release["size"] == patch.stat().st_size


def test_feed_source_env_override(monkeypatch) -> None:
    """Переменная окружения важнее адреса по умолчанию."""

    monkeypatch.setenv(
        update_channel.FEED_ENV,
        "https://example.org/feed.json",
    )

    assert update_channel.feed_source() == "https://example.org/feed.json"


def test_feed_source_default_per_platform(monkeypatch) -> None:
    """Без переменной адрес ведёт на GitHub и знает платформу."""

    monkeypatch.delenv(update_channel.FEED_ENV, raising=False)

    source = update_channel.feed_source()

    assert source.startswith(update_channel.RELEASE_FEED_BASE)
    assert source.endswith(
        f"releases-{update_channel.feed_platform()}.json"
    )


def test_feed_is_readable_by_update_service(tmp_path) -> None:
    """Сгенерированный каталог разбирается сервисом обновлений."""

    app = _app(tmp_path)
    patch = tmp_path / "patch.zip"

    update_feed.pack_patch(app, patch)

    document = update_feed.build_feed(
        version="9.9.9",
        target="linux",
        patch=patch,
        url="https://example.org/patch.zip",
    )

    feed_file = tmp_path / "releases.json"
    feed_file.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )

    feed = update_service.load_feed(str(feed_file))

    assert feed.releases[0].version == "9.9.9"
    assert feed.releases[0].has_patch
