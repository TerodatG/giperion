# Giperion/tests/test_update_service.py                             v001
# Обновления терминала: версии, каталог выпусков, патчи и установка.
# Последнее изменение: первый набор — от сравнения версий до распаковки.

import json
import zipfile
from types import SimpleNamespace

import pytest

from terminal.core import app_version, update_service
from terminal.core.app_version import is_newer, version_key
from terminal.core.update_service import (
    Release,
    UpdateError,
    apply_update,
    check_for_updates,
    download_update,
    patch_file_name,
    release_for,
)


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Изолирует проект, каталог обновлений и файл состояния."""

    root = tmp_path / "project"
    root.mkdir()

    data = root / "data"
    data.mkdir()

    updates = root / "updates"
    feed = data / "releases.json"
    state = data / "update_state.json"

    monkeypatch.setattr(update_service, "PROJECT_ROOT", root)
    monkeypatch.setattr(update_service, "UPDATES_DIR", updates)
    monkeypatch.setattr(update_service, "FEED_FILE", feed)
    monkeypatch.setattr(app_version, "STATE_FILE", state)

    return SimpleNamespace(
        root=root,
        data=data,
        updates=updates,
        feed=feed,
        state=state,
    )


def write_feed(path, releases: list[dict], channel: str = "stable") -> None:
    """Пишет каталог выпусков для проверки."""

    document = {
        "version": "v001",
        "app": "Giperion Terminal",
        "channel": channel,
        "updated": "2026-10-25",
        "releases": releases,
    }

    path.write_text(
        json.dumps(document, ensure_ascii=False),
        encoding="utf-8",
    )


def make_zip(path, files: dict[str, bytes]):
    """Собирает архив патча из словаря «путь — содержимое»."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)

    return path


def test_version_keys_compare_by_numbers() -> None:
    """Версии сравниваются по числам, а не по строкам."""

    assert is_newer("1.1.0", "1.0.0")
    assert is_newer("1.0.10", "1.0.9")
    assert is_newer("v2.0", "1.9.9")
    assert not is_newer("1.0.0", "1.0.0")
    assert not is_newer("0.9.0", "1.0.0")
    assert not is_newer("", "1.0.0")


def test_version_key_ignores_suffix() -> None:
    """Хвост вроде beta не мешает сравнению."""

    assert version_key("1.2.3-beta") == (1, 2, 3)
    assert version_key("версия 2.0") == (2, 0)


def test_patch_name_has_version_and_date() -> None:
    """Файл патча получает имя с версией и датой."""

    release = Release(version="1.1.0", date="2026-11-01")

    assert patch_file_name(release) == "giperion-1.1.0-2026-11-01.patch"


def test_patch_name_sanitizes_odd_versions() -> None:
    """Опасные символы в версии не попадают в имя файла."""

    release = Release(version="1.1.0/../evil", date="2026-11-01")

    name = patch_file_name(release)

    assert name.startswith("giperion-1.1.0")
    assert "/" not in name
    assert ".." not in name
    assert name.endswith(".patch")


def test_check_finds_newer_release(sandbox) -> None:
    """Проверка находит выпуски новее установленного."""

    write_feed(
        sandbox.feed,
        [
            {"version": "1.0.0", "date": "2026-10-25"},
            {"version": "1.2.0", "date": "2026-12-01"},
            {"version": "1.1.0", "date": "2026-11-01"},
        ],
    )

    check = check_for_updates()

    assert check.error == ""
    assert check.current == "1.0.0"
    assert [item.version for item in check.new_releases] == [
        "1.2.0",
        "1.1.0",
    ]
    assert check.available.version == "1.2.0"
    assert check.up_to_date is False
    assert check.channel == "stable"
    assert "releases.json" in check.source


def test_check_reports_latest_version(sandbox) -> None:
    """Если новее ничего нет, проверка это и сообщает."""

    write_feed(sandbox.feed, [{"version": "1.0.0"}])

    check = check_for_updates()

    assert check.new_releases == []
    assert check.up_to_date is True
    assert check.available is None


def test_check_survives_missing_feed(sandbox) -> None:
    """Пропавший каталог выпусков не роняет окно."""

    check = check_for_updates(str(sandbox.root / "нет-такого.json"))

    assert check.error
    assert check.up_to_date is False
    assert check.available is None


def test_feed_sorts_releases_newest_first(sandbox) -> None:
    """Каталог отдаёт выпуски от свежего к старому."""

    write_feed(
        sandbox.feed,
        [
            {"version": "0.8.0"},
            {"version": "1.0.0"},
            {"version": "0.9.0"},
        ],
    )

    check = check_for_updates()

    assert [item.version for item in check.releases] == [
        "1.0.0",
        "0.9.0",
        "0.8.0",
    ]


def test_release_for_finds_version() -> None:
    """Выпуск находится по версии, даже с приставкой v."""

    releases = [
        Release(version="1.1.0"),
        Release(version="1.0.0"),
    ]

    assert release_for("v1.1.0", releases).version == "1.1.0"
    assert release_for("9.9.9", releases) is None


def test_download_writes_named_patch(sandbox) -> None:
    """Патч ложится в updates под именем с версией и датой."""

    source = make_zip(
        sandbox.root / "source.patch",
        {"docs/new.md": b"hello"},
    )

    release = Release(
        version="1.1.0",
        date="2026-11-01",
        patch=str(source),
    )

    patch = download_update(release)

    assert patch.path.name == "giperion-1.1.0-2026-11-01.patch"
    assert patch.path.parent == sandbox.updates
    assert patch.path.is_file()
    assert patch.size == source.stat().st_size
    assert len(patch.sha256) == 64
    assert not list(sandbox.updates.glob("*.part"))


def test_download_rejects_bad_checksum(sandbox) -> None:
    """Подменённый патч не сохраняется."""

    source = make_zip(
        sandbox.root / "source.patch",
        {"docs/new.md": b"hello"},
    )

    release = Release(
        version="1.1.0",
        date="2026-11-01",
        patch=str(source),
        sha256="0" * 64,
    )

    with pytest.raises(UpdateError):
        download_update(release)

    assert not list(sandbox.updates.glob("*.patch"))


def test_download_needs_patch_file(sandbox) -> None:
    """Выпуск без файла патча скачивать нечего."""

    with pytest.raises(UpdateError):
        download_update(Release(version="1.1.0"))


def test_apply_writes_files_and_bumps_version(sandbox) -> None:
    """Установка распаковывает патч, сохраняет копию и меняет версию."""

    existing = sandbox.root / "docs" / "guide.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("старая версия", encoding="utf-8")

    source = make_zip(
        sandbox.root / "patch.zip",
        {
            "docs/guide.md": b"new version",
            "docs/fresh.md": b"brand new",
        },
    )

    release = Release(version="1.1.0", date="2026-11-01")

    result = apply_update(source, release)

    assert result.version == "1.1.0"
    assert result.files == ["docs/fresh.md", "docs/guide.md"]
    assert result.requires_restart is True
    assert existing.read_text(encoding="utf-8") == "new version"
    assert (sandbox.root / "docs" / "fresh.md").is_file()

    # Резервная копия хранит прежнее содержимое.
    assert result.backup_dir is not None
    backup = result.backup_dir / "docs" / "guide.md"
    assert backup.read_text(encoding="utf-8") == "старая версия"

    # Версия запомнена в файле состояния.
    assert app_version.current_version() == "1.1.0"
    assert app_version.current_patch() == "patch.zip"
    assert json.loads(sandbox.state.read_text(encoding="utf-8"))[
        "installed"
    ] == "1.1.0"


def test_apply_rejects_path_traversal(sandbox) -> None:
    """Патч не может писать за пределы папки проекта."""

    source = make_zip(
        sandbox.root / "evil.zip",
        {"../outside.txt": b"bad"},
    )

    with pytest.raises(UpdateError):
        apply_update(source, Release(version="6.6.6"))

    assert not (sandbox.root.parent / "outside.txt").exists()
    assert app_version.current_version() == "1.0.0"


def test_apply_rejects_git_folder(sandbox) -> None:
    """Служебные папки проекта патч не трогает."""

    source = make_zip(
        sandbox.root / "git.zip",
        {".git/config": b"bad"},
    )

    with pytest.raises(UpdateError):
        apply_update(source, Release(version="6.6.6"))


def test_apply_rejects_plain_file(sandbox) -> None:
    """Не архив — не патч для установки."""

    plain = sandbox.root / "notes.patch"
    plain.write_text("просто текст", encoding="utf-8")

    with pytest.raises(UpdateError):
        apply_update(plain, Release(version="1.1.0"))


def test_apply_rechecks_checksum(sandbox) -> None:
    """Повреждённый после скачивания патч не устанавливается."""

    source = make_zip(
        sandbox.root / "patch.zip",
        {"docs/new.md": b"hello"},
    )

    release = Release(
        version="1.1.0",
        date="2026-11-01",
        sha256="0" * 64,
    )

    with pytest.raises(UpdateError):
        apply_update(source, release)

    assert app_version.current_version() == "1.0.0"
