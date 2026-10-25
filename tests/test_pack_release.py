# Giperion/tests/test_pack_release.py                               v001
# Сборка патча выпуска: архив, сумма и запись в каталог.
# Последнее изменение: первый тест — публикация выпуска в каталог.

import json
import zipfile

import pytest

from terminal.core import update_service
from tools import pack_release
from tools.pack_release import publish_release


@pytest.fixture()
def project(tmp_path, monkeypatch):
    """Готовит маленький проект с каталогом выпусков."""

    root = tmp_path / "project"
    (root / "docs").mkdir(parents=True)
    (root / "data").mkdir()

    monkeypatch.setattr(pack_release, "BASE_DIR", root)
    monkeypatch.setattr(update_service, "BASE_DIR", root)

    feed = root / "data" / "releases.json"
    feed.write_text(
        json.dumps(
            {
                "version": "v001",
                "app": "Giperion Terminal",
                "channel": "stable",
                "releases": [
                    {"version": "0.9.0", "date": "2026-10-20"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return root, feed


def test_publish_release_builds_patch(project) -> None:
    """Выпуск добавляет патч в updates/feed и запись в каталог."""

    root, feed = project

    (root / "docs" / "release.md").write_text(
        "Заметки выпуска",
        encoding="utf-8",
    )

    result = publish_release(
        "1.1.0",
        "2026-11-01",
        "Терминал 1.1",
        ["Первое изменение", "Второе изменение"],
        ["docs/release.md"],
        feed_file=feed,
        output_dir=root / "updates" / "feed",
    )

    assert result["patch"] == (
        "updates/feed/giperion-1.1.0-2026-11-01.patch"
    )
    assert result["files"] == 1
    assert len(result["sha256"]) == 64

    patch = root / result["patch"]

    assert patch.is_file()
    assert result["size"] == patch.stat().st_size
    assert zipfile.is_zipfile(patch)

    with zipfile.ZipFile(patch) as archive:
        assert archive.namelist() == ["docs/release.md"]

    document = json.loads(feed.read_text(encoding="utf-8"))

    assert [item["version"] for item in document["releases"]] == [
        "1.1.0",
        "0.9.0",
    ]

    entry = document["releases"][0]

    assert entry["title"] == "Терминал 1.1"
    assert entry["notes"] == [
        "Первое изменение",
        "Второе изменение",
    ]
    assert entry["sha256"] == result["sha256"]
    assert entry["size"] > 0


def test_publish_same_version_replaces_entry(project) -> None:
    """Повторная публикация версии заменяет запись, а не дублирует."""

    root, feed = project

    (root / "docs" / "release.md").write_text("v1", encoding="utf-8")

    for text in ("первый", "второй"):
        (root / "docs" / "release.md").write_text(
            text,
            encoding="utf-8",
        )
        publish_release(
            "1.1.0",
            "2026-11-01",
            "",
            [],
            ["docs/release.md"],
            feed_file=feed,
            output_dir=root / "updates" / "feed",
        )

    document = json.loads(feed.read_text(encoding="utf-8"))

    assert [item["version"] for item in document["releases"]] == [
        "1.1.0",
        "0.9.0",
    ]


def test_publish_needs_files(project) -> None:
    """Без файлов публиковать нечего."""

    root, feed = project

    with pytest.raises(SystemExit):
        publish_release(
            "1.1.0",
            "2026-11-01",
            "",
            [],
            [],
            feed_file=feed,
            output_dir=root / "updates" / "feed",
        )
